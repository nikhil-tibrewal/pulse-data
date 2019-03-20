# Recidiviz - a platform for tracking granular recidivism metrics in real time
# Copyright (C) 2018 Recidiviz, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# =============================================================================
"""Contains logic to match database entities with ingested entities."""

import logging
from collections import defaultdict
from typing import List, Dict, Tuple, Set, Sequence, Callable, Any, cast

from opencensus.stats import measure, view, aggregation

from recidiviz import Session
from recidiviz.common import common_utils
from recidiviz.common.constants.bond import BondStatus
from recidiviz.common.constants.charge import ChargeStatus
from recidiviz.common.constants.hold import HoldStatus
from recidiviz.common.constants.sentence import SentenceStatus
from recidiviz.persistence import entity_matching_utils as utils, entities
from recidiviz.persistence.database import database
from recidiviz.persistence.entities import Entity
from recidiviz.persistence.errors import MatchedMultipleDatabaseEntitiesError, \
    MatchedMultipleIngestedEntitiesError, EntityMatchingError
from recidiviz.utils import monitoring

m_matching_errors = measure.MeasureInt(
    'persistence/entity_matching/error_count',
    'Number of EntityMatchingErrors thrown for a specific entity type', '1')

matching_errors_by_entity_view = view.View(
    'recidiviz/persistence/entity_matching/error_count',
    'Sum of the errors in the entit matching layer, by entity',
    [monitoring.TagKey.REGION, monitoring.TagKey.ENTITY_TYPE],
    m_matching_errors,
    aggregation.SumAggregation())

monitoring.register_views([matching_errors_by_entity_view])


def match(
        session: Session, region: str,
        ingested_people: List[entities.Person]) -> Tuple[int, List[Entity]]:
    """Attempts to match all people from |ingested_people| with corresponding
    people in our database for the given |region|. For any ingested person, if a
    matching person exists in the database, the primary key is updated on the
    ingested person.

    Returns a tuple with the following:
        - error count (int): The number of errors raised while entity matching
            the provided |ingested_people|
        - orphaned entities (List[Entity]): All entities that were orphaned
            during matching. These will need to be added to the session
            separately from the matched people.
    """

    with_external_ids = []
    without_external_ids = []

    for ingested_person in ingested_people:
        if ingested_person.external_id:
            with_external_ids.append(ingested_person)
        else:
            without_external_ids.append(ingested_person)

    error_count = 0
    orphaned_entities: List[Entity] = []
    if with_external_ids:
        db_people_with_external_ids = database.read_people_by_external_ids(
            session, region, with_external_ids)
        error_count += match_people_and_return_error_count(
            db_people=db_people_with_external_ids,
            ingested_people=with_external_ids,
            orphaned_entities=orphaned_entities)

    if without_external_ids:
        db_people_without_external_ids = \
            database.read_people_with_open_bookings(
                session, region, without_external_ids)
        error_count += match_people_and_return_error_count(
            db_people=db_people_without_external_ids,
            ingested_people=without_external_ids,
            orphaned_entities=orphaned_entities)

    return error_count, orphaned_entities


def match_people_and_return_error_count(
        *, db_people: List[entities.Person],
        ingested_people: List[entities.Person],
        orphaned_entities: List[Entity]) -> int:
    """
    Attempts to match all people from |ingested_people| with people from the
    |db_people|. For any ingested person, if a matching person exists in
    |db_people|, the primary key is updated on the ingested person.
    """
    error_count = 0
    matched_people_by_db_id: Dict[int, entities.Person] = {}
    for ingested_person in ingested_people:
        try:
            match_person(ingested_person=ingested_person, db_people=db_people,
                         orphaned_entities=orphaned_entities,
                         matched_people_by_db_id=matched_people_by_db_id)
        except EntityMatchingError as e:
            logging.exception(
                'Found error while matching ingested person. \nPerson: %s',
                ingested_person)
            increment_error(e.entity_name)
            error_count += 1
    return error_count


def match_person(
        *, ingested_person: entities.Person,
        db_people: List[entities.Person],
        orphaned_entities: List[Entity],
        matched_people_by_db_id: Dict[int, entities.Person]) -> None:
    db_person: entities.Person = _get_only_match(ingested_person, db_people,
                                                 utils.is_person_match)
    if db_person:
        logging.debug('Successfully matched to person with ID %s',
                      db_person.person_id)
        # If the match was previously matched to a different database
        # person, raise an error.
        if db_person.person_id in matched_people_by_db_id:
            matches = [ingested_person,
                       matched_people_by_db_id[db_person.person_id]]
            raise MatchedMultipleIngestedEntitiesError(db_person, matches)
        ingested_person.person_id = db_person.person_id
        matched_people_by_db_id[
            cast(int, db_person.person_id)] = ingested_person
        match_bookings(db_person=db_person, ingested_person=ingested_person,
                       orphaned_entities=orphaned_entities)


def match_bookings(
        *, db_person: entities.Person, ingested_person: entities.Person,
        orphaned_entities: List[Entity]):
    """
    Attempts to match all bookings on the |ingested_person| with bookings on
    the |db_person|. For any ingested booking, if a matching booking exists on
    |db_person|, the primary key is updated on the ingested booking.
    """
    matched_bookings_by_db_id: Dict[int, entities.Booking] = {}
    for ingested_booking in ingested_person.bookings:
        db_booking: entities.Booking = \
            _get_only_match(ingested_booking, db_person.bookings,
                            utils.is_booking_match)
        if db_booking:
            logging.debug('Successfully matched to booking with ID %s',
                          db_booking.booking_id)
            # If the match was previously matched to a different database
            # booking, raise an error.
            if db_booking.booking_id in matched_bookings_by_db_id:
                matches = [ingested_booking,
                           matched_bookings_by_db_id[db_booking.booking_id]]
                raise MatchedMultipleIngestedEntitiesError(db_booking, matches)
            matched_bookings_by_db_id[
                cast(int, db_booking.booking_id)] = ingested_booking
            ingested_booking.booking_id = db_booking.booking_id

            if (db_booking.admission_date_inferred and
                    ingested_booking.admission_date_inferred):
                ingested_booking.admission_date = db_booking.admission_date
                ingested_booking.admission_date_inferred = True

            match_arrest(db_booking=db_booking,
                         ingested_booking=ingested_booking)
            match_holds(db_booking=db_booking,
                        ingested_booking=ingested_booking)
            match_charges(db_booking=db_booking,
                          ingested_booking=ingested_booking)
            match_bonds(db_booking=db_booking,
                        ingested_booking=ingested_booking,
                        orphaned_entities=orphaned_entities)
            match_sentences(db_booking=db_booking,
                            ingested_booking=ingested_booking,
                            orphaned_entities=orphaned_entities)

    for db_booking in db_person.bookings:
        if db_booking.booking_id not in matched_bookings_by_db_id:
            ingested_person.bookings.append(db_booking)


def match_bonds(
        *, db_booking: entities.Booking, ingested_booking: entities.Booking,
        orphaned_entities: List[Entity]):
    _match_from_charges(db_booking=db_booking,
                        ingested_booking=ingested_booking, name='bond',
                        orphaned_entities=orphaned_entities)


def match_sentences(
        *, db_booking: entities.Booking, ingested_booking: entities.Booking,
        orphaned_entities: List[Entity]):
    _match_from_charges(db_booking=db_booking,
                        ingested_booking=ingested_booking, name='sentence',
                        orphaned_entities=orphaned_entities)


def _build_maps_from_charges(
        charges: List[entities.Charge], obj_name: str) \
        -> Tuple[Dict[str, Entity], Dict[str, Set[Entity]], Dict[int, str]]:
    """Helper function that returns a pair of maps describing the relationships
    between charges and their children. The |object_map| maps ids, which may be
    temporary generated ids, to the objects they refer to. The
    |object_relationships| map maps those ids to the set of charges that the
    object is a child of. This is part of determining entity equality,
    e.g. two bonds are equal only if the same set of charges has the bond as its
    child."""
    object_map = {}
    object_relationships: Dict[str, set] = defaultdict(set)
    id_to_generated: Dict[int, str] = {}

    for charge in charges:
        obj = getattr(charge, obj_name)
        if obj:
            obj_id = getattr(obj, obj_name + '_id')
            if not obj_id:
                obj_id = id_to_generated.get(id(obj)) or \
                         common_utils.create_generated_id()
                id_to_generated[id(obj)] = obj_id
            object_map[obj_id] = obj
            object_relationships[obj_id].add(charge.charge_id)
    return object_map, object_relationships, id_to_generated


def _match_from_charges(
        *, db_booking: entities.Booking, ingested_booking: entities.Booking,
        name: str, orphaned_entities: List[Entity]):
    """Helper function that, within a booking, matches objects that are children
    of the booking's charges. |name| should be 'bond' or 'sentence'.

    Any entities that are orphaned as a part of this process are added to the
    given |orphaned_entities|.
    """
    id_name = name + '_id'
    db_obj_map, db_relationship_map, _ = _build_maps_from_charges(
        db_booking.charges, name)
    ing_obj_map, ing_relationship_map, id_to_generated = \
        _build_maps_from_charges(ingested_booking.charges, name)

    def _is_match_with_relationships(*, db_entity, ingested_entity):
        ing_entity_id = id_to_generated[id(ingested_entity)]
        db_entity_id = getattr(db_entity, id_name)
        matcher = getattr(utils, 'is_{}_match'.format(name))
        obj_match = matcher(db_entity=db_entity,
                            ingested_entity=ingested_entity)
        # The relationships "match" if new relationships have been added
        # since the last scrape, but not if relationships have been removed.
        relationship_match = db_relationship_map[db_entity_id].issubset(
            ing_relationship_map[ing_entity_id])

        return obj_match and relationship_match

    matched_ing_objs_by_db_id: Dict[int, entities.Entity] = {}
    for ing_obj in ing_obj_map.values():
        db_obj = _get_next_available_match(
            ing_obj, list(db_obj_map.values()), matched_ing_objs_by_db_id,
            _is_match_with_relationships)
        if db_obj:
            db_id = getattr(db_obj, name + '_id')
            logging.debug('successfully matched to %s with id %s',
                          name, db_id)
            setattr(ing_obj, name + '_id', db_id)
            matched_ing_objs_by_db_id[cast(int, db_id)] = ing_obj

    for db_obj in db_obj_map.values():
        if not getattr(db_obj, id_name) in matched_ing_objs_by_db_id:
            logging.debug('Did not match %s to any ingested %s, dropping',
                          getattr(db_obj, id_name), name)
            drop_fn = globals()['_drop_' + name]
            drop_fn(db_obj)
            orphaned_entities.append(db_obj)


def _drop_sentence(sentence: entities.Sentence):
    if sentence.status != SentenceStatus.REMOVED_WITHOUT_INFO:
        logging.debug('Removing sentence with id %s', sentence.sentence_id)
        sentence.status = SentenceStatus.REMOVED_WITHOUT_INFO


def _drop_bond(bond: entities.Bond):
    if bond.status != BondStatus.REMOVED_WITHOUT_INFO:
        logging.debug('Removing bond with id %s', bond.bond_id)
        bond.status = BondStatus.REMOVED_WITHOUT_INFO


def match_arrest(
        *, db_booking: entities.Booking, ingested_booking: entities.Booking):
    if db_booking.arrest and ingested_booking.arrest:
        ingested_booking.arrest.arrest_id = db_booking.arrest.arrest_id


def match_holds(
        *, db_booking: entities.Booking, ingested_booking: entities.Booking):
    """
    Attempts to match all holds on the |ingested_booking| with holds on
    the |db_booking|. For any ingested hold, if a matching hold exists on
    |db_booking|, the primary key is updated on the ingested hold. All
    db holds that are not matched to an ingested hold are marked dropped and
    added to the |ingested_booking|.
    """

    matched_holds_by_db_id: Dict[int, entities.Hold] = {}
    for ingested_hold in ingested_booking.holds:
        db_hold: entities.Hold = _get_only_match(
            ingested_hold, db_booking.holds, utils.is_hold_match)

        if db_hold:
            logging.debug(
                'Successfully matched to hold with ID %s', db_hold.hold_id)

            # If the match was previously matched to a different database
            # charge, raise an error.
            if db_hold.hold_id in matched_holds_by_db_id:
                matches = [ingested_hold,
                           matched_holds_by_db_id[db_hold.hold_id]]
                raise MatchedMultipleIngestedEntitiesError(db_hold, matches)

            ingested_hold.hold_id = db_hold.hold_id
            matched_holds_by_db_id[cast(int, db_hold.hold_id)] = ingested_hold

    dropped_holds = []
    for db_hold in db_booking.holds:
        if db_hold.hold_id not in matched_holds_by_db_id:
            _drop_hold(db_hold)
            dropped_holds.append(db_hold)
    ingested_booking.holds.extend(dropped_holds)


def _drop_hold(hold: entities.Hold):
    if hold.status != HoldStatus.INFERRED_DROPPED:
        logging.debug('Dropping hold with id %s', hold.hold_id)
        hold.status = HoldStatus.INFERRED_DROPPED


def _charge_relationship_count(charge: entities.Charge) -> int:
    """Return the number of children that the supplied |charge| contains"""
    return sum([bool(charge.bond), bool(charge.sentence)])


def match_charges(
        *, db_booking: entities.Booking, ingested_booking: entities.Booking):
    """
    Attempts to match all charges on the |ingested_booking| with charges on
    the |db_booking|. For any ingested charge, if a matching charge exists on
    |db_booking|, the primary key is updated on the ingested charge. All
    db charges that are not matched to an ingested charge are marked dropped and
    added to the |ingested_booking|.

    Note about charge matching:

    Our matching scheme here is designed to reduce turnover with our charge,
    sentence, an bond entities (i.e. preferring to update entities rather than
    replacing old ones).

    If possible, we match ingested_charges to db_charges while considering
    the equality of their children (bonds/sentences). If we cannot match an
    ingested_charge while considering its children, we attempt to match it only
    based on the charge fields. If the ingested_charge still has no match,
    it will be marked dropped.

    Because we can match two charges whose children are not equal, we sort our
    ingested_charges, attempting to match those with more children before
    those with fewer or none.

    Examples:
        1. Two identical charges are ingested, one with a bond (A) and one
        without (B). The same charges were also scraped yesterday, and are in
        our DB as charge C (with a bond) and D (without a bond)

        Because A could match either C or D, we sort our ingested charges by the
        number of children, so that we always attempt to match A before B. This
        ensures A matches to C, and then B matches to D.

        If we attempted to match B before A, B could match to C, causing a new
        bond to be added to B. Then A would match to D, and its bond would be
        dropped. This turnover is not desired.

        2. We scrape one charge from the website (A), and this charge is exactly
        the same as a charge in our DB (B), except that the ingested charge A
        now has a bond. In this case we'll first try to match A considering
        the child bond, and when no matches are found, we'll match just
        considering the charge fields. At this point A matches to B,
        and B gets a new bond created in the DB.
    """
    matched_charges_by_db_id: Dict[int, entities.Charge] = {}
    ing_charges_sorted_by_child_count = sorted(
        ingested_booking.charges, key=_charge_relationship_count, reverse=True)

    for ingested_charge in ing_charges_sorted_by_child_count:
        db_charge: entities.Charge = _get_next_available_match(
            ingested_charge, db_booking.charges,
            matched_charges_by_db_id, utils.is_charge_match_with_children)

        if not db_charge:
            db_charge = _get_next_available_match(
                ingested_charge, db_booking.charges, matched_charges_by_db_id,
                utils.is_charge_match)

        if db_charge:
            logging.debug('Successfully matched to charge with ID %s',
                          db_charge.charge_id)
            matched_charges_by_db_id[
                cast(int, db_charge.charge_id)] = ingested_charge
            ingested_charge.charge_id = db_charge.charge_id

    dropped_charges = []
    for db_charge in db_booking.charges:
        if db_charge.charge_id not in matched_charges_by_db_id:
            _drop_charge(db_charge)
            dropped_charges.append(db_charge)
    ingested_booking.charges.extend(dropped_charges)


def _drop_charge(charge: entities.Charge):
    if charge.status != ChargeStatus.INFERRED_DROPPED:
        logging.debug('Dropping charge with id %s', charge.charge_id)
        charge.status = ChargeStatus.INFERRED_DROPPED


def _get_next_available_match(
        ingested_entity: entities.Entity,
        db_entities: Sequence[entities.Entity],
        db_entities_matched_by_id: Dict[int, Any],
        matcher: Callable):
    id_name = ingested_entity.get_entity_name() + '_id'

    for db_entity in db_entities:
        if not getattr(db_entity, id_name) in db_entities_matched_by_id and \
                matcher(db_entity=db_entity, ingested_entity=ingested_entity):
            return db_entity
    return None


def _get_only_match(
        ingested_entity: entities.Entity,
        db_entities: Sequence[entities.Entity], matcher: Callable):
    """
       Finds the entity in |db_entites| that matches the |ingested_entity|.
       Args:
           ingested_entity: an entity ingested from source (usually website)
           db_entities: List of entities from our db that are potential matches
               for the |ingested_entity|
           matcher:
               (db_entity, ingested_entity) -> (bool)
       Returns:
           The entity from |db_entities| that matches the |ingested_entity|,
           or None if no match is found.
       Raises:
           EntityMatchingError: if more than one match is found.
       """
    matches = _get_all_matches(ingested_entity, db_entities, matcher)
    if len(matches) > 1:
        raise MatchedMultipleDatabaseEntitiesError(ingested_entity, matches)
    return matches[0] if matches else None


def _get_all_matches(
        ingested_entity: entities.Entity,
        db_entities: Sequence[entities.Entity], matcher: Callable):
    return [db_entity for db_entity in db_entities
            if matcher(db_entity=db_entity, ingested_entity=ingested_entity)]


def increment_error(entity_name: str) -> None:
    mtags = {monitoring.TagKey.ENTITY_TYPE: entity_name}
    with monitoring.measurements(mtags) as measurements:
        measurements.measure_int_put(m_matching_errors, 1)
