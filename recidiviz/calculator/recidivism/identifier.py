# Recidiviz - a data platform for criminal justice reform
# Copyright (C) 2019 Recidiviz, Inc.
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

"""Identifies instances of recidivism and non-recidivism for calculation.

This contains the core logic for identifying recidivism events on a
person-by-person basis, transforming incarceration periods for a given person
into instances of recidivism or non-recidivism as appropriate.


"""
from datetime import date
import logging
from typing import Dict, List, Optional

from collections import defaultdict
from recidiviz.calculator.recidivism.release_event import \
    ReincarcerationReturnType, ReincarcerationReturnFromSupervisionType, \
    ReleaseEvent, RecidivismReleaseEvent, NonRecidivismReleaseEvent
from recidiviz.common.constants.state.state_incarceration_period import \
    StateIncarcerationPeriodStatus
from recidiviz.common.constants.state.state_incarceration_period import \
    StateIncarcerationPeriodAdmissionReason as AdmissionReason
from recidiviz.common.constants.state.state_incarceration_period import \
    StateIncarcerationPeriodReleaseReason as ReleaseReason
from recidiviz.persistence.entity.state.entities import StateIncarcerationPeriod


def find_release_events_by_cohort_year(
        incarceration_periods: List[StateIncarcerationPeriod]) \
        -> Dict[int, List[ReleaseEvent]]:
    """Finds instances of release and determines if they resulted in recidivism.

    Transforms each StateIncarcerationPeriod from which the person has been
    released into a mapping from its release cohort to the details of the event.
    The release cohort is an integer for the year, e.g. 2006. The event details
    are a ReleaseEvent object, which can represent events of both recidivism and
    non-recidivism. That is, each StateIncarcerationPeriod is transformed into a
    recidivism event unless it is the most recent period of incarceration and
    they are still incarcerated, or it is connected to a subsequent
    StateIncarcerationPeriod by a transfer.

    Example output for someone who went to prison in 2006, was released in 2008,
    went back in 2010, was released in 2012, and never returned:
    {
      2008: [RecidivismReleaseEvent(original_admission_date="2006-04-05", ...)],
      2012: [NonRecidivismReleaseEvent(original_admission_date="2010-09-17",
                ...)]
    }

    Args:
        incarceration_periods: list of StateIncarcerationPeriods for a person

    Returns:
        A dictionary mapping release cohorts to a list of ReleaseEvents
            for the given person in that cohort.
    """

    incarceration_periods = \
        validate_sort_and_collapse_incarceration_periods(incarceration_periods)

    release_events: Dict[int, List[ReleaseEvent]] = defaultdict(list)

    for index, incarceration_period in enumerate(incarceration_periods):

        admission_date = incarceration_period.admission_date
        status = incarceration_period.status
        release_date = incarceration_period.release_date
        release_reason = incarceration_period.release_reason
        release_facility = incarceration_period.facility

        if not admission_date:
            # This should never happen after validation. Throw error.
            raise ValueError("admission_date should not be None on "
                             f"{incarceration_period}.")

        if not status:
            # This should never happen after validation. Throw error.
            raise ValueError("status should not be None on "
                             f"{incarceration_period}.")

        if index == len(incarceration_periods) - 1:
            event = for_last_incarceration_period(admission_date, status,
                                                  release_date,
                                                  release_reason,
                                                  release_facility)
        else:
            reincarceration_period = incarceration_periods[index + 1]
            reincarceration_date = reincarceration_period.admission_date
            reincarceration_facility = reincarceration_period.facility
            reincarceration_admission_reason = \
                reincarceration_period.admission_reason

            if not release_date:
                # This should never happen after validation. Throw error.
                raise ValueError("release_date should not be None on an"
                                 "intermediate incarceration period "
                                 f"{incarceration_period}.")

            if not release_reason:
                # This should never happen after validation. Throw error.
                raise ValueError("release_reason should not be None on an "
                                 "intermediate incarceration period "
                                 f"{incarceration_period}.")

            if not reincarceration_date:
                # This should never happen after validation. Throw error.
                raise ValueError("reincarceration_date should "
                                 f"not be None on {incarceration_period}.")

            if not reincarceration_admission_reason:
                # This should never happen after validation. Throw error.
                raise ValueError("reincarceration_admission_reason should "
                                 f"not be None on {incarceration_period}.")

            event = for_intermediate_incarceration_period(
                admission_date, release_date, release_reason, release_facility,
                reincarceration_date, reincarceration_facility,
                reincarceration_admission_reason)

        if event:
            if not release_date:
                raise ValueError("Release event should not have been generated"
                                 "with a null release_date.")
            release_cohort = release_date.year
            release_events[release_cohort].append(event)

    return release_events


def validate_sort_and_collapse_incarceration_periods(
        incarceration_periods: List[StateIncarcerationPeriod]) -> \
        List[StateIncarcerationPeriod]:
    """Validates, sorts, and collapses the incarceration period inputs.

    Ensures the necessary dates are set on each incarceration period. Sorts the
    the list of StateIncarcerationPeriods sorted by admission_date, and
    collapses the ones connected by a transfer.
    """
    for incarceration_period in incarceration_periods:
        if not incarceration_period.admission_date:
            raise ValueError("No admission_date on incarceration period: "
                             f"{incarceration_period}")
        if not incarceration_period.admission_reason:
            raise ValueError("No admission_reason on incarceration period: "
                             f"{incarceration_period}")
        if not incarceration_period.status:
            raise ValueError("No status on incarceration period: "
                             f"{incarceration_period}")
        if not incarceration_period.release_date and \
                incarceration_period.status != \
                StateIncarcerationPeriodStatus.IN_CUSTODY:
            raise ValueError("No release_date on intermediate incarceration "
                             f"period: {incarceration_period}")
        if not incarceration_period.release_reason and \
                incarceration_period.status != \
                StateIncarcerationPeriodStatus.IN_CUSTODY:
            raise ValueError("No release_reason on intermediate incarceration "
                             f"period: {incarceration_period}")

    incarceration_periods.sort(key=lambda b: b.admission_date)

    incarceration_periods = \
        collapse_incarceration_periods(incarceration_periods)

    return incarceration_periods


def collapse_incarceration_periods(incarceration_periods:
                                   List[StateIncarcerationPeriod]) -> \
        List[StateIncarcerationPeriod]:
    """Collapses any incarceration periods that are connected by transfers.

    Loops through all of the StateIncarcerationPeriods and combines adjacent
    periods that are connected by a transfer. Only connects two periods if the
    release reason of the first is `TRANSFER` and the admission reason for the
    second is also `TRANSFER`.

    Args:
        incarceration_periods: list of StateIncarcerationPeriods for a
            StatePerson

    Returns:
        A list of collapsed StateIncarcerationPeriods.
    """

    new_incarceration_periods: List[StateIncarcerationPeriod] = []
    open_transfer = False

    # TODO(1782): Check to see if back to back incarceration periods are related
    #  to the same StateIncarcerationSentence or SentenceGroup to be sure we
    #  aren't counting stacked sentences or related periods as recidivism.
    for incarceration_period in incarceration_periods:
        if open_transfer:
            if incarceration_period.admission_reason == \
                    AdmissionReason.TRANSFER:
                # If there is an open transfer period and they were transferred
                # into this incarceration period, then combine this period with
                # the open transfer period.
                start_period = new_incarceration_periods.pop(-1)
                combined_period = \
                    combine_incarceration_periods(start_period,
                                                  incarceration_period)
                new_incarceration_periods.append(combined_period)
            else:
                # They weren't transferred here. Add this as a new
                # incarceration period.
                # TODO(1790): Analyze how often a transfer out is followed by an
                #  admission type that isn't a transfer to ensure we aren't
                #  making bad assumptions with this transfer logic.
                new_incarceration_periods.append(incarceration_period)
        else:
            # TODO(1790): Analyze how often an incarceration period that starts
            #  with a transfer in is not preceded by a transfer out of a
            #  different facility.
            new_incarceration_periods.append(incarceration_period)

        # If this incarceration period ended in a transfer, then flag
        # that there's an open transfer period.
        open_transfer = (incarceration_period.release_reason ==
                         ReleaseReason.TRANSFER)

    return new_incarceration_periods


def combine_incarceration_periods(start: StateIncarcerationPeriod,
                                  end: StateIncarcerationPeriod) -> \
        StateIncarcerationPeriod:
    """Combines two StateIncarcerationPeriods.

    Brings together two StateIncarcerationPeriods by setting the following
    fields on the |start| StateIncarcerationPeriod to the values on the |end|
    StateIncarcerationPeriod:

        [status, release_date, facility, housing_unit, facility_security_level,
        facility_security_level_raw_text, projected_release_reason,
        projected_release_reason_raw_text, release_reason,
        release_reason_raw_text]

        Args:
            start: The starting StateIncarcerationPeriod.
            end: The ending StateIncarcerationPeriod.
    """

    start.status = end.status
    start.release_date = end.release_date
    start.facility = end.facility
    start.housing_unit = end.housing_unit
    start.facility_security_level = end.facility_security_level
    start.facility_security_level_raw_text = \
        end.facility_security_level_raw_text
    start.projected_release_reason = end.projected_release_reason
    start.projected_release_reason_raw_text = \
        end.projected_release_reason_raw_text
    start.release_reason = end.release_reason
    start.release_reason_raw_text = end.release_reason_raw_text

    return start


def for_last_incarceration_period(
        admission_date: date,
        status: StateIncarcerationPeriodStatus,
        release_date: Optional[date],
        release_reason: Optional[ReleaseReason],
        release_facility: Optional[str]) \
        -> Optional[ReleaseEvent]:
    """Looks at the last StateIncarcerationPeriod for a non-recidivism event.

    If the person has been released from their last StateIncarcerationPeriod,
    there is an instance of non-recidivism to count. If they are still
    incarcerated, or they were released for some circumstances, e.g. because
    they died, there is nothing to count. Returns any non-recidivism event
    relevant to the person's last StateIncarcerationPeriod.

        Args:
            admission_date: when this StateIncarcerationPeriod started
            status: status of this StateIncarcerationPeriod
            release_date: when they were released from this
                 StateIncarcerationPeriod
            release_reason: reason they were released from this
                StateIncarcerationPeriod
            release_facility: the facility they were released from on this
                StateIncarcerationPeriod


        Returns:
            A non-recidivism event if released legitimately from this
                StateIncarcerationPeriod. None otherwise.
        """

    # If the person is still in custody, there is nothing to track.
    if status == StateIncarcerationPeriodStatus.IN_CUSTODY:
        return None

    if not release_date:
        # If the person is not in custody, there should be a release_date.
        # This should not happen after validation. Throw error.
        raise ValueError("release_date is not set where it should be.")

    if release_reason == ReleaseReason.DEATH:
        # If the person was released from this incarceration period because they
        # died, do not include them in the release cohort.
        return None
    if release_reason in (ReleaseReason.ESCAPE,
                          ReleaseReason.RELEASED_IN_ERROR):
        # If the person was released from this incarceration period but was not
        # meant to be released, do not include them in the release cohort.
        return None
    if release_reason == ReleaseReason.TRANSFER:
        # If the person was released from this incarceration period because they
        # were transferred elsewhere, do not include them in the release cohort.
        return None
    if release_reason in [ReleaseReason.CONDITIONAL_RELEASE,
                          ReleaseReason.SENTENCE_SERVED]:

        return NonRecidivismReleaseEvent(admission_date, release_date,
                                         release_facility)

    raise ValueError("Enum case not handled for "
                     "StateIncarcerationPeriodReleaseReason of type:"
                     f" {release_reason}.")


def for_intermediate_incarceration_period(
        admission_date: date,
        release_date: date,
        release_reason: ReleaseReason,
        release_facility: Optional[str],
        reincarceration_date: date,
        reincarceration_facility: Optional[str],
        reincarceration_admission_reason: AdmissionReason) -> \
        Optional[ReleaseEvent]:
    """Returns the ReleaseEvent relevant to an intermediate
    StateIncarcerationPeriod.

    If this is not the person's last StateIncarcerationPeriod and they have been
    released, there is probably an instance of recidivism to count.

    Args:
        admission_date: when the StateIncarcerationPeriod started
        release_date: when they were released from the StateIncarcerationPeriod
        release_reason: the reason they were released from the
            StateIncarcerationPeriod
        release_facility: the facility they were released from on the
            StateIncarcerationPeriod
        reincarceration_date: date they were admitted to the subsequent
            StateIncarcerationPeriod
        reincarceration_facility: facility in which the subsequent
            StateIncarcerationPeriod started
        reincarceration_admission_reason: reason they were admitted to the
            subsequent StateIncarcerationPeriod

    Returns:
        A ReleaseEvent.
    """

    if not should_include_in_release_cohort(release_reason,
                                            reincarceration_admission_reason):
        # Don't include this release in the release cohort
        return None

    return_type = get_return_type(reincarceration_admission_reason)
    from_supervision_type = \
        get_from_supervision_type(reincarceration_admission_reason)

    # This is a new admission recidivism event. Return it.
    return RecidivismReleaseEvent(admission_date, release_date,
                                  release_facility, reincarceration_date,
                                  reincarceration_facility, return_type,
                                  from_supervision_type)


def should_include_in_release_cohort(
        release_reason: ReleaseReason,
        reincarceration_admission_reason: AdmissionReason) -> bool:
    """Identifies whether a pair of release reason and admission reason should
    be included in the release cohort."""

    if release_reason == ReleaseReason.DEATH:
        # If there is an intermediate incarceration period with a release reason
        # of death, log this unexpected situation.
        logging.info("StateIncarcerationPeriod following a release for death.")
        return False
    if release_reason == ReleaseReason.ESCAPE:
        # If this escape is followed by a reincarceration_admission_reason that
        # is not RETURN_FROM_ESCAPE, log this unexpected situation.
        if reincarceration_admission_reason != \
                AdmissionReason.RETURN_FROM_ESCAPE:
            logging.info("%s following a release for ESCAPE.",
                         reincarceration_admission_reason)

        # If the person was released from this incarceration period because they
        # escaped, do not include them in the release cohort.
        return False
    if release_reason == ReleaseReason.RELEASED_IN_ERROR:
        if reincarceration_admission_reason != \
                AdmissionReason.RETURN_FROM_ERRONEOUS_RELEASE:
            logging.info("%s following an erroneous release.",
                         reincarceration_admission_reason)
        # If the person was released from this incarceration period due to an
        # error, do not include them in the release cohort.
        return False
    if release_reason == ReleaseReason.TRANSFER:
        # The fact that this transfer release reason isn't collapsed with a
        # transfer admission reason means there is something unexpected going
        # on. Log it.
        logging.warning("Unexpected reincarceration_admission_reason: %s "
                        "following a release for a transfer.",
                        reincarceration_admission_reason)

        # If the person was released from this incarceration period because they
        # were transferred elsewhere, do not include them in the release cohort.
        return False
    if release_reason in (ReleaseReason.COMMUTED,
                          ReleaseReason.CONDITIONAL_RELEASE,
                          ReleaseReason.COURT_ORDER,
                          ReleaseReason.EXTERNAL_UNKNOWN,
                          ReleaseReason.SENTENCE_SERVED):
        if reincarceration_admission_reason in (
                AdmissionReason.RETURN_FROM_ESCAPE,
                AdmissionReason.RETURN_FROM_ERRONEOUS_RELEASE):
            # If this person was not recorded as escaped, but returned on a
            # release from escape, log this unexpected situation and exclude
            # from the release cohort.
            logging.info("Unexpected reincarceration_admission_reason of "
                         "%s following a release reason of %s.",
                         reincarceration_admission_reason, release_reason)
            return False

        return True

    raise ValueError("Enum case not handled for "
                     "StateIncarcerationPeriodReleaseReason of type:"
                     f" {release_reason}.")


def get_return_type(
        reincarceration_admission_reason: AdmissionReason) -> \
        ReincarcerationReturnType:
    """Returns the return type for the reincarceration admission reason."""

    if reincarceration_admission_reason == AdmissionReason.ADMITTED_IN_ERROR:
        return ReincarcerationReturnType.NEW_ADMISSION
    if reincarceration_admission_reason == AdmissionReason.EXTERNAL_UNKNOWN:
        return ReincarcerationReturnType.NEW_ADMISSION
    if reincarceration_admission_reason == AdmissionReason.NEW_ADMISSION:
        return ReincarcerationReturnType.NEW_ADMISSION
    if reincarceration_admission_reason == AdmissionReason.PAROLE_REVOCATION:
        return ReincarcerationReturnType.REVOCATION
    if reincarceration_admission_reason == AdmissionReason.PROBATION_REVOCATION:
        return ReincarcerationReturnType.REVOCATION
    if reincarceration_admission_reason == AdmissionReason.TRANSFER:
        # This should be a rare case, but we are considering this a type of
        # new admission recidivism because this person became reincarcerated at
        # some point after being released, and this is the most likely return
        # type in most cases in the absence of further information."
        return ReincarcerationReturnType.NEW_ADMISSION
    if reincarceration_admission_reason in (
            AdmissionReason.RETURN_FROM_ESCAPE,
            AdmissionReason.RETURN_FROM_ERRONEOUS_RELEASE):
        # This should never happen. Should have been filtered by
        # should_include_in_release_cohort function. Throw error.
        raise ValueError("should_include_in_release_cohort is not effectively"
                         " filtering. Found unexpected admission_reason of:"
                         f" {reincarceration_admission_reason}")

    raise ValueError("Enum case not handled for "
                     "StateIncarcerationPeriodAdmissionReason of type:"
                     f" {reincarceration_admission_reason}.")


def get_from_supervision_type(
        reincarceration_admission_reason: AdmissionReason) \
        -> Optional[ReincarcerationReturnFromSupervisionType]:
    """If the person returned from supervision, returns the type."""

    if reincarceration_admission_reason in [AdmissionReason.ADMITTED_IN_ERROR,
                                            AdmissionReason.EXTERNAL_UNKNOWN,
                                            AdmissionReason.NEW_ADMISSION]:
        return None
    if reincarceration_admission_reason == AdmissionReason.PAROLE_REVOCATION:
        return ReincarcerationReturnFromSupervisionType.PAROLE
    if reincarceration_admission_reason == AdmissionReason.PROBATION_REVOCATION:
        return ReincarcerationReturnFromSupervisionType.PROBATION
    if reincarceration_admission_reason in (
            AdmissionReason.RETURN_FROM_ESCAPE,
            AdmissionReason.RETURN_FROM_ERRONEOUS_RELEASE,
            AdmissionReason.TRANSFER):
        # This should never happen. Should have been filtered by
        # should_include_in_release_cohort function. Throw error.
        raise ValueError("should_include_in_release_cohort is not effectively"
                         " filtering. Found unexpected admission_reason of:"
                         f" {reincarceration_admission_reason}")

    raise ValueError("Enum case not handled for "
                     "StateIncarcerationPeriodAdmissionReason of type:"
                     f" {reincarceration_admission_reason}.")
