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

# pylint: disable=unused-import,wrong-import-order

"""Tests for recidivism/pipeline.py."""

import unittest

import apache_beam as beam
from apache_beam.testing.util import assert_that, equal_to, BeamAssertException
from apache_beam.testing.test_pipeline import TestPipeline

from datetime import date
from dateutil.relativedelta import relativedelta
import pytest

from recidiviz.calculator.recidivism import pipeline
from recidiviz.calculator.recidivism import calculator, \
    ReincarcerationRecidivismMetric
from recidiviz.calculator.recidivism.metrics import RecidivismMethodologyType
from recidiviz.calculator.recidivism.release_event import \
    ReincarcerationReturnType, ReleaseEvent, RecidivismReleaseEvent, \
    NonRecidivismReleaseEvent
from recidiviz.common.constants.state.state_incarceration_period import \
    StateIncarcerationPeriodStatus, StateIncarcerationPeriodAdmissionReason, \
    StateIncarcerationPeriodReleaseReason, \
    StateIncarcerationFacilitySecurityLevel
from recidiviz.persistence.database.schema.state import schema
from recidiviz.persistence.entity.state.entities import StatePerson, \
    StateIncarcerationPeriod, Gender, Race, ResidencyStatus, Ethnicity
from recidiviz.persistence.entity.state.entities import StatePerson
from recidiviz.tests.calculator.calculator_test_utils import \
    normalized_database_base_dict, normalized_database_base_dict_list
from recidiviz.calculator.utils import extractor_utils


class TestRecidivismPipeline(unittest.TestCase):
    """Tests the entire recidivism pipeline."""

    def testRecidivismPipeline(self):
        """Tests the entire recidivism pipeline with one person and three
        incarceration periods."""

        fake_person_id = 12345

        fake_person = schema.StatePerson(
            person_id=fake_person_id, gender=Gender.MALE,
            birthdate=date(1970, 1, 1),
            residency_status=ResidencyStatus.PERMANENT)

        persons_data = [normalized_database_base_dict(fake_person)]

        race_1 = schema.StatePersonRace(
            person_race_id=111,
            state_code='CA',
            race=Race.BLACK,
            person_id=fake_person_id
        )

        race_2 = schema.StatePersonRace(
            person_race_id=111,
            state_code='ND',
            race=Race.WHITE,
            person_id=fake_person_id
        )

        races_data = normalized_database_base_dict_list([race_1, race_2])

        ethnicity = schema.StatePersonEthnicity(
            person_ethnicity_id=111,
            state_code='CA',
            ethnicity=Ethnicity.HISPANIC,
            person_id=fake_person_id)

        ethnicity_data = normalized_database_base_dict_list([ethnicity])

        initial_incarceration = schema.StateIncarcerationPeriod(
            incarceration_period_id=1111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='CA',
            county_code='124',
            facility='San Quentin',
            facility_security_level=StateIncarcerationFacilitySecurityLevel.
            MAXIMUM,
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
            projected_release_reason=StateIncarcerationPeriodReleaseReason.
            CONDITIONAL_RELEASE,
            admission_date=date(2008, 11, 20),
            release_date=date(2010, 12, 4),
            release_reason=StateIncarcerationPeriodReleaseReason.
            SENTENCE_SERVED,
            person_id=fake_person_id
        )

        first_reincarceration = schema.StateIncarcerationPeriod(
            incarceration_period_id=2222,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='CA',
            county_code='124',
            facility='San Quentin',
            facility_security_level=StateIncarcerationFacilitySecurityLevel.
            MAXIMUM,
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
            projected_release_reason=StateIncarcerationPeriodReleaseReason.
            CONDITIONAL_RELEASE,
            admission_date=date(2011, 4, 5),
            release_date=date(2014, 4, 14),
            release_reason=StateIncarcerationPeriodReleaseReason.
            SENTENCE_SERVED,
            person_id=fake_person_id)

        subsequent_reincarceration = schema.StateIncarcerationPeriod(
            incarceration_period_id=3333,
            status=StateIncarcerationPeriodStatus.IN_CUSTODY,
            state_code='CA',
            county_code='124',
            facility='San Quentin',
            facility_security_level=StateIncarcerationFacilitySecurityLevel.
            MAXIMUM,
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
            projected_release_reason=StateIncarcerationPeriodReleaseReason.
            CONDITIONAL_RELEASE,
            admission_date=date(2017, 1, 4),
            person_id=fake_person_id)

        incarceration_periods_data = [
            normalized_database_base_dict(initial_incarceration),
            normalized_database_base_dict(first_reincarceration),
            normalized_database_base_dict(subsequent_reincarceration)
        ]

        dimensions_to_filter = ['age_bucket', 'race', 'release_facility',
                                'stay_length_bucket', 'ethnicity']

        methodologies = [RecidivismMethodologyType.EVENT,
                         RecidivismMethodologyType.PERSON]

        data_dict = {schema.StatePerson.__tablename__: persons_data,
                     schema.StatePersonRace.__tablename__: races_data,
                     schema.StatePersonEthnicity.__tablename__: ethnicity_data,
                     schema.StateIncarcerationPeriod.__tablename__:
                         incarceration_periods_data}

        test_pipeline = TestPipeline()

        # Get StatePersons
        persons = (
            test_pipeline
            | 'Load Persons' >>
            extractor_utils.BuildRootEntity(
                dataset=None,
                data_dict=data_dict,
                root_schema_class=schema.StatePerson,
                root_entity_class=StatePerson,
                unifying_id_field='person_id'))

        # Get StateIncarcerationPeriods
        incarceration_periods = (
            test_pipeline
            | 'Load IncarcerationPeriods' >>
            extractor_utils.BuildRootEntity(
                dataset=None,
                data_dict=data_dict,
                root_schema_class=schema.StateIncarcerationPeriod,
                root_entity_class=StateIncarcerationPeriod,
                unifying_id_field='person_id'))

        # Group each StatePerson with their StateIncarcerationPeriods
        person_and_incarceration_periods = \
            ({'person': persons,
              'incarceration_periods': incarceration_periods}
             | 'Group StatePerson to StateIncarcerationPeriods' >>
             beam.CoGroupByKey()
             )

        # Identify ReleaseEvents events from the StatePerson's
        # StateIncarcerationPeriods
        person_events = (person_and_incarceration_periods |
                         'Get Release Events' >>
                         pipeline.GetReleaseEvents())

        recidivism_metrics = (person_events
                              | 'Get Recidivism Metrics' >>
                              pipeline.GetRecidivismMetrics())

        filter_metrics_kwargs = {
            'dimensions_to_filter_out': dimensions_to_filter,
            'methodologies': methodologies,
            'release_count_min': 0}

        # Filter out unneeded metrics
        filtered_metrics = (recidivism_metrics
                            | 'Filter out unwanted metrics' >>
                            beam.ParDo(pipeline.FilterMetrics(),
                                       **filter_metrics_kwargs))

        assert_that(filtered_metrics, AssertMatchers.validate_pipeline_test())

        test_pipeline.run()

    def testRecidivismPipeline_WithConditionalReturns(self):
        """Tests the entire RecidivismPipeline with two person and three
        incarceration periods each. One StatePerson has a return from a
        supervision violation.
        """

        fake_person_id_1 = 12345

        fake_person_1 = schema.StatePerson(
            person_id=fake_person_id_1, gender=Gender.MALE,
            birthdate=date(1970, 1, 1),
            residency_status=ResidencyStatus.PERMANENT)

        fake_person_id_2 = 6789

        fake_person_2 = schema.StatePerson(
            person_id=fake_person_id_2, gender=Gender.FEMALE,
            birthdate=date(1990, 1, 1),
            residency_status=ResidencyStatus.PERMANENT)

        persons_data = [normalized_database_base_dict(fake_person_1),
                        normalized_database_base_dict(fake_person_2)]

        initial_incarceration_1 = schema.StateIncarcerationPeriod(
            incarceration_period_id=1111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='CA',
            county_code='124',
            facility='San Quentin',
            facility_security_level=StateIncarcerationFacilitySecurityLevel.
            MAXIMUM,
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
            projected_release_reason=StateIncarcerationPeriodReleaseReason.
            CONDITIONAL_RELEASE,
            admission_date=date(2008, 11, 20),
            release_date=date(2010, 12, 4),
            release_reason=StateIncarcerationPeriodReleaseReason.
            SENTENCE_SERVED,
            person_id=fake_person_id_1)

        first_reincarceration_1 = schema.StateIncarcerationPeriod(
            incarceration_period_id=2222,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='CA',
            county_code='124',
            facility='San Quentin',
            facility_security_level=StateIncarcerationFacilitySecurityLevel.
            MAXIMUM,
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
            projected_release_reason=StateIncarcerationPeriodReleaseReason.
            CONDITIONAL_RELEASE,
            admission_date=date(2011, 4, 5),
            release_date=date(2014, 4, 14),
            release_reason=StateIncarcerationPeriodReleaseReason.
            SENTENCE_SERVED,
            person_id=fake_person_id_1)

        subsequent_reincarceration_1 = \
            schema.StateIncarcerationPeriod(
                incarceration_period_id=3333,
                status=StateIncarcerationPeriodStatus.IN_CUSTODY,
                state_code='CA',
                county_code='124',
                facility='San Quentin',
                facility_security_level=StateIncarcerationFacilitySecurityLevel.
                MAXIMUM,
                admission_reason=StateIncarcerationPeriodAdmissionReason.
                NEW_ADMISSION,
                projected_release_reason=StateIncarcerationPeriodReleaseReason.
                CONDITIONAL_RELEASE,
                admission_date=date(2017, 1, 4),
                person_id=fake_person_id_1)

        initial_incarceration_2 = schema.StateIncarcerationPeriod(
            incarceration_period_id=4444,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='CA',
            county_code='124',
            facility='San Quentin',
            facility_security_level=StateIncarcerationFacilitySecurityLevel.
            MAXIMUM,
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
            projected_release_reason=StateIncarcerationPeriodReleaseReason.
            CONDITIONAL_RELEASE,
            admission_date=date(2004, 12, 20),
            release_date=date(2010, 6, 3),
            release_reason=StateIncarcerationPeriodReleaseReason.
            CONDITIONAL_RELEASE,
            person_id=fake_person_id_2)

        first_reincarceration_2 = schema.StateIncarcerationPeriod(
            incarceration_period_id=5555,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='CA',
            county_code='124',
            facility='San Quentin',
            facility_security_level=StateIncarcerationFacilitySecurityLevel.
            MAXIMUM,
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            PAROLE_REVOCATION,
            projected_release_reason=StateIncarcerationPeriodReleaseReason.
            CONDITIONAL_RELEASE,
            admission_date=date(2011, 4, 5),
            release_date=date(2014, 1, 4),
            release_reason=StateIncarcerationPeriodReleaseReason.
            SENTENCE_SERVED,
            person_id=fake_person_id_2)

        subsequent_reincarceration_2 = \
            schema.StateIncarcerationPeriod(
                incarceration_period_id=6666,
                status=StateIncarcerationPeriodStatus.IN_CUSTODY,
                state_code='CA',
                county_code='124',
                facility='San Quentin',
                facility_security_level=StateIncarcerationFacilitySecurityLevel.
                MAXIMUM,
                admission_reason=StateIncarcerationPeriodAdmissionReason.
                NEW_ADMISSION,
                projected_release_reason=StateIncarcerationPeriodReleaseReason.
                CONDITIONAL_RELEASE,
                admission_date=date(2018, 3, 9),
                person_id=fake_person_id_2)

        incarceration_periods_data = [
            normalized_database_base_dict(initial_incarceration_1),
            normalized_database_base_dict(first_reincarceration_1),
            normalized_database_base_dict(subsequent_reincarceration_1),
            normalized_database_base_dict(initial_incarceration_2),
            normalized_database_base_dict(first_reincarceration_2),
            normalized_database_base_dict(subsequent_reincarceration_2)
        ]

        dimensions_to_filter = ['age_bucket', 'race', 'release_facility',
                                'stay_length_bucket']

        methodologies = [RecidivismMethodologyType.EVENT,
                         RecidivismMethodologyType.PERSON]

        data_dict = {schema.StatePerson.__tablename__: persons_data,
                     schema.StateIncarcerationPeriod.__tablename__:
                         incarceration_periods_data}

        test_pipeline = TestPipeline()

        # Get StatePersons
        persons = (test_pipeline
                   | 'Get Persons' >>
                   extractor_utils.BuildRootEntity(
                       dataset=None,
                       data_dict=data_dict,
                       root_schema_class=schema.StatePerson,
                       root_entity_class=StatePerson,
                       unifying_id_field='person_id'))

        # Get StateIncarcerationPeriods
        incarceration_periods = (
            test_pipeline
            | 'Get IncarcerationPeriods' >>
            extractor_utils.BuildRootEntity(
                dataset=None,
                data_dict=data_dict,
                root_schema_class=schema.StateIncarcerationPeriod,
                root_entity_class=StateIncarcerationPeriod,
                unifying_id_field='person_id'))

        # Group each StatePerson with their StateIncarcerationPeriods
        person_and_incarceration_periods = \
            ({'person': persons,
              'incarceration_periods': incarceration_periods}
             | 'Group StatePerson to StateIncarcerationPeriods' >>
             beam.CoGroupByKey()
             )

        # Classify ReleaseEvents from the StatePerson's
        # StateIncarcerationPeriods
        person_events = (person_and_incarceration_periods |
                         'Get Release Events' >>
                         pipeline.GetReleaseEvents())

        recidivism_metrics = (person_events
                              | 'Get Recidivism Metrics' >>
                              pipeline.GetRecidivismMetrics())

        filter_metrics_kwargs = {
            'dimensions_to_filter_out': dimensions_to_filter,
            'methodologies': methodologies,
            'release_count_min': 0}

        # Filter out unneeded metrics
        filtered_metrics = (recidivism_metrics
                            | 'Filter out unwanted metrics' >>
                            beam.ParDo(pipeline.FilterMetrics(),
                                       **filter_metrics_kwargs))

        assert_that(filtered_metrics, AssertMatchers.validate_pipeline_test())

        test_pipeline.run()


class TestClassifyReleaseEvents(unittest.TestCase):
    """Tests the ClassifyReleaseEvents DoFn in the pipeline."""

    def testClassifyReleaseEvents(self):
        """Tests the ClassifyReleaseEvents DoFn when there are two instances
        of recidivism."""

        fake_person_id = 12345

        fake_person = StatePerson.new_with_defaults(
            person_id=fake_person_id, gender=Gender.MALE,
            birthdate=date(1970, 1, 1),
            residency_status=ResidencyStatus.PERMANENT)

        initial_incarceration = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=1111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 11, 20),
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
            release_date=date(2010, 12, 4),
            release_reason=StateIncarcerationPeriodReleaseReason.
            SENTENCE_SERVED)

        first_reincarceration = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=2222,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2011, 4, 5),
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
            release_date=date(2014, 4, 14),
            release_reason=StateIncarcerationPeriodReleaseReason.
            SENTENCE_SERVED)

        subsequent_reincarceration = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=3333,
            status=StateIncarcerationPeriodStatus.IN_CUSTODY,
            state_code='TX',
            admission_date=date(2017, 1, 4),
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION)

        person_incarceration_periods = {'person': [fake_person],
                                        'incarceration_periods': [
                                            initial_incarceration,
                                            first_reincarceration,
                                            subsequent_reincarceration]}

        first_recidivism_release_event = RecidivismReleaseEvent(
            original_admission_date=initial_incarceration.admission_date,
            release_date=initial_incarceration.release_date,
            release_facility=None,
            reincarceration_date=first_reincarceration.admission_date,
            reincarceration_facility=None,
            return_type=ReincarcerationReturnType.NEW_ADMISSION)

        second_recidivism_release_event = RecidivismReleaseEvent(
            original_admission_date=first_reincarceration.admission_date,
            release_date=first_reincarceration.release_date,
            release_facility=None,
            reincarceration_date=subsequent_reincarceration.admission_date,
            reincarceration_facility=None,
            return_type=ReincarcerationReturnType.NEW_ADMISSION)

        correct_output = [
            (fake_person, {initial_incarceration.release_date.year:
                           [first_recidivism_release_event],
                           first_reincarceration.release_date.year:
                           [second_recidivism_release_event]})]

        test_pipeline = TestPipeline()

        output = (test_pipeline
                  | beam.Create([(fake_person_id,
                                  person_incarceration_periods)])
                  | 'Identify Recidivism Events' >>
                  beam.ParDo(pipeline.ClassifyReleaseEvents())
                  )

        assert_that(output, equal_to(correct_output))

        test_pipeline.run()

    def testClassifyReleaseEvents_NoRecidivism(self):
        """Tests the ClassifyReleaseEvents DoFn in the pipeline when there
        is no instance of recidivism."""

        fake_person_id = 12345

        fake_person = StatePerson.new_with_defaults(
            person_id=fake_person_id, gender=Gender.MALE,
            birthdate=date(1970, 1, 1),
            residency_status=ResidencyStatus.PERMANENT)

        only_incarceration = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=1111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX', admission_date=date(2008, 11, 20),
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
            release_date=date(2010, 12, 4),
            release_reason=StateIncarcerationPeriodReleaseReason.
            SENTENCE_SERVED)

        person_incarceration_periods = {'person': [fake_person],
                                        'incarceration_periods':
                                            [only_incarceration]}

        non_recidivism_release_event = NonRecidivismReleaseEvent(
            only_incarceration.admission_date, only_incarceration.release_date,
            only_incarceration.facility)

        correct_output = [(fake_person,
                           {only_incarceration.release_date.year:
                            [non_recidivism_release_event]})]

        test_pipeline = TestPipeline()

        output = (test_pipeline
                  | beam.Create([(fake_person_id,
                                  person_incarceration_periods)])
                  | 'Identify Recidivism Events' >>
                  beam.ParDo(pipeline.ClassifyReleaseEvents()))

        assert_that(output, equal_to(correct_output))

        test_pipeline.run()

    def testClassifyReleaseEvents_NoIncarcerationPeriods(self):
        """Tests the ClassifyReleaseEvents DoFn in the pipeline when there
        are no incarceration periods."""

        fake_person_id = 12345

        fake_person = StatePerson.new_with_defaults(
            person_id=fake_person_id, gender=Gender.MALE,
            birthdate=date(1970, 1, 1),
            residency_status=ResidencyStatus.PERMANENT)

        person_incarceration_periods = {'person': [fake_person],
                                        'incarceration_periods': []}

        correct_output = [(fake_person, {})]

        test_pipeline = TestPipeline()

        output = (test_pipeline
                  | beam.Create([(fake_person_id,
                                  person_incarceration_periods)])
                  | 'Identify Recidivism Events' >>
                  beam.ParDo(pipeline.ClassifyReleaseEvents())
                  )

        assert_that(output, equal_to(correct_output))

        test_pipeline.run()

    def testClassifyReleaseEvents_TwoReleasesSameYear(self):
        """Tests the ClassifyReleaseEvents DoFn in the pipeline when a person
        is released twice in the same calendar year."""

        fake_person_id = 12345

        fake_person = StatePerson.new_with_defaults(
            person_id=fake_person_id, gender=Gender.MALE,
            birthdate=date(1970, 1, 1),
            residency_status=ResidencyStatus.PERMANENT)

        initial_incarceration = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=1111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 11, 20),
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
            release_date=date(2010, 1, 4),
            release_reason=StateIncarcerationPeriodReleaseReason.
            SENTENCE_SERVED)

        first_reincarceration = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=2222,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2010, 4, 5),
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
            release_date=date(2010, 10, 14),
            release_reason=StateIncarcerationPeriodReleaseReason.
            SENTENCE_SERVED)

        subsequent_reincarceration = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=3333,
            status=StateIncarcerationPeriodStatus.IN_CUSTODY,
            state_code='TX',
            admission_date=date(2017, 1, 4),
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
        )

        person_incarceration_periods = {'person': [fake_person],
                                        'incarceration_periods': [
                                            initial_incarceration,
                                            first_reincarceration,
                                            subsequent_reincarceration]}

        first_recidivism_release_event = RecidivismReleaseEvent(
            original_admission_date=initial_incarceration.admission_date,
            release_date=initial_incarceration.release_date,
            release_facility=None,
            reincarceration_date=first_reincarceration.admission_date,
            reincarceration_facility=None,
            return_type=ReincarcerationReturnType.NEW_ADMISSION)

        second_recidivism_release_event = RecidivismReleaseEvent(
            original_admission_date=first_reincarceration.admission_date,
            release_date=first_reincarceration.release_date,
            release_facility=None,
            reincarceration_date=subsequent_reincarceration.admission_date,
            reincarceration_facility=None,
            return_type=ReincarcerationReturnType.NEW_ADMISSION)

        correct_output = [
            (fake_person, {initial_incarceration.release_date.year:
                           [first_recidivism_release_event,
                            second_recidivism_release_event]})]

        test_pipeline = TestPipeline()
        output = (test_pipeline
                  | beam.Create([(fake_person_id,
                                  person_incarceration_periods)])
                  | 'Identify Recidivism Events' >>
                  beam.ParDo(pipeline.ClassifyReleaseEvents())
                  )

        assert_that(output, equal_to(correct_output))

        test_pipeline.run()

    def testClassifyReleaseEvents_WrongOrder(self):
        """Tests the ClassifyReleaseEvents DoFn when there are two instances
        of recidivism."""

        fake_person_id = 12345

        fake_person = StatePerson.new_with_defaults(
            person_id=fake_person_id, gender=Gender.MALE,
            birthdate=date(1970, 1, 1),
            residency_status=ResidencyStatus.PERMANENT)

        initial_incarceration = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=1111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 11, 20),
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
            release_date=date(2010, 12, 4),
            release_reason=StateIncarcerationPeriodReleaseReason.
            SENTENCE_SERVED)

        first_reincarceration = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=2222,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2011, 4, 5),
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION,
            release_date=date(2014, 4, 14),
            release_reason=StateIncarcerationPeriodReleaseReason.
            SENTENCE_SERVED)

        subsequent_reincarceration = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=3333,
            status=StateIncarcerationPeriodStatus.IN_CUSTODY,
            state_code='TX',
            admission_date=date(2017, 1, 4),
            admission_reason=StateIncarcerationPeriodAdmissionReason.
            NEW_ADMISSION)

        person_incarceration_periods = {'person': [fake_person],
                                        'incarceration_periods': [
                                            subsequent_reincarceration,
                                            initial_incarceration,
                                            first_reincarceration]}

        first_recidivism_release_event = RecidivismReleaseEvent(
            original_admission_date=initial_incarceration.admission_date,
            release_date=initial_incarceration.release_date,
            release_facility=None,
            reincarceration_date=first_reincarceration.admission_date,
            reincarceration_facility=None,
            return_type=ReincarcerationReturnType.NEW_ADMISSION)

        second_recidivism_release_event = RecidivismReleaseEvent(
            original_admission_date=first_reincarceration.admission_date,
            release_date=first_reincarceration.release_date,
            release_facility=None,
            reincarceration_date=subsequent_reincarceration.admission_date,
            reincarceration_facility=None,
            return_type=ReincarcerationReturnType.NEW_ADMISSION)

        correct_output = [
            (fake_person, {initial_incarceration.release_date.year:
                           [first_recidivism_release_event],
                           first_reincarceration.release_date.year:
                           [second_recidivism_release_event]})]

        test_pipeline = TestPipeline()

        output = (test_pipeline
                  | beam.Create([(fake_person_id,
                                  person_incarceration_periods)])
                  | 'Identify Recidivism Events' >>
                  beam.ParDo(pipeline.ClassifyReleaseEvents())
                  )

        assert_that(output, equal_to(correct_output))

        test_pipeline.run()


class TestCalculateRecidivismMetricCombinations(unittest.TestCase):
    """Tests for the CalculateRecidivismMetricCombinations DoFn in the
    pipeline."""

    def testCalculateRecidivismMetricCombinations(self):
        """Tests the CalculateRecidivismMetricCombinations DoFn in the
        pipeline."""

        fake_person_id = 12345

        fake_person = StatePerson.new_with_defaults(
            person_id=fake_person_id, gender=Gender.MALE,
            residency_status=ResidencyStatus.PERMANENT)

        first_recidivism_release_event = RecidivismReleaseEvent(
            original_admission_date=date(2008, 11, 20),
            release_date=date(2010, 12, 4), release_facility=None,
            reincarceration_date=date(2011, 4, 5),
            reincarceration_facility=None,
            return_type=ReincarcerationReturnType.NEW_ADMISSION)

        second_recidivism_release_event = RecidivismReleaseEvent(
            original_admission_date=date(2011, 4, 5),
            release_date=date(2014, 4, 14), release_facility=None,
            reincarceration_date=date(2017, 1, 4),
            reincarceration_facility=None,
            return_type=ReincarcerationReturnType.NEW_ADMISSION)

        person_events = [
            (fake_person, {first_recidivism_release_event.release_date.year:
                           [first_recidivism_release_event],
                           second_recidivism_release_event.release_date.year:
                               [second_recidivism_release_event]})]

        # Get the number of combinations of person-event characteristics.
        num_combinations = len(calculator.characteristic_combinations(
            fake_person, first_recidivism_release_event))
        assert num_combinations > 0

        # We do not track metrics for periods that start after today, so we
        # need to subtract for some number of periods that go beyond whatever
        # today is.
        periods = relativedelta(date.today(), date(2010, 12, 4)).years + 1
        periods_with_single = 6
        periods_with_double = periods - periods_with_single

        expected_combinations_count_2010 = \
            ((num_combinations * 2 * periods_with_single) +
             (num_combinations * 3 * periods_with_double))

        periods = relativedelta(date.today(), date(2014, 4, 14)).years + 1

        expected_combinations_count_2014 = num_combinations * 2 * periods

        expected_combination_counts = {2010: expected_combinations_count_2010,
                                       2014: expected_combinations_count_2014}

        test_pipeline = TestPipeline()

        output = (test_pipeline
                  | beam.Create(person_events)
                  | 'Calculate Metric Combinations' >>
                  beam.ParDo(pipeline.CalculateRecidivismMetricCombinations())
                  )

        assert_that(output, AssertMatchers.
                    count_combinations(expected_combination_counts))

        test_pipeline.run()

    def testCalculateRecidivismMetricCombinations_NoResults(self):
        """Tests the CalculateRecidivismMetricCombinations DoFn in the pipeline
        when there are no ReleaseEvents associated with the StatePerson."""

        fake_person_id = 12345

        fake_person = StatePerson.new_with_defaults(
            person_id=fake_person_id, gender=Gender.MALE,
            residency_status=ResidencyStatus.PERMANENT)

        person_events = [(fake_person, {})]

        test_pipeline = TestPipeline()

        output = (test_pipeline
                  | beam.Create(person_events)
                  | 'Calculate Metric Combinations' >>
                  beam.ParDo(pipeline.CalculateRecidivismMetricCombinations())
                  )

        assert_that(output, equal_to([]))

        test_pipeline.run()

    def testCalculateRecidivismMetricCombinations_NoPersonEvents(self):
        """Tests the CalculateRecidivismMetricCombinations DoFn in the pipeline
        when there is no StatePerson and no ReleaseEvents."""

        person_events = []

        test_pipeline = TestPipeline()

        output = (test_pipeline
                  | beam.Create(person_events)
                  | 'Calculate Metric Combinations' >>
                  beam.ParDo(pipeline.CalculateRecidivismMetricCombinations())
                  )

        assert_that(output, equal_to([]))

        test_pipeline.run()


class TestProduceReincarcerationRecidivismMetric(unittest.TestCase):
    """Tests for the ProduceReincarcerationRecidivismMetric DoFn in the
     pipeline."""

    def testProduceReincarcerationRecidivismMetric(self):
        """Tests the ProduceReincarcerationRecidivismMetric DoFn in the
         pipeline."""

        metric_key = {'stay_length': '36-48', 'gender': Gender.MALE,
                      'release_cohort': 2014,
                      'methodology': RecidivismMethodologyType.PERSON,
                      'follow_up_period': 1}

        release_group = [1, 0, 1, 0, 0, 0, 1, 1, 1, 1]
        expected_recidivism_rate = \
            (sum(release_group) + 0.0) / len(release_group)

        test_pipeline = TestPipeline()

        output = (test_pipeline
                  | beam.Create([(metric_key, release_group)])
                  | 'Produce Recidivism Metric' >>
                  beam.ParDo(pipeline.ProduceReincarcerationRecidivismMetric())
                  )

        assert_that(output, AssertMatchers.
                    validate_recidivism_metric(expected_recidivism_rate))

        test_pipeline.run()

    def testProduceReincarcerationRecidivismMetric_NoRecidivism(self):
        """Tests the ProduceRecivismMetric DoFn in the pipeline when the
        recidivism rate for the metric is 0.0."""

        metric_key = {'stay_length': '36-48', 'gender': Gender.MALE,
                      'release_cohort': 2014,
                      'methodology': RecidivismMethodologyType.PERSON,
                      'follow_up_period': 1}

        release_group = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        expected_recidivism_rate = \
            (sum(release_group) + 0.0) / len(release_group)

        test_pipeline = TestPipeline()

        output = (test_pipeline
                  | beam.Create([(metric_key, release_group)])
                  | 'Produce Recidivism Metric' >>
                  beam.ParDo(pipeline.ProduceReincarcerationRecidivismMetric())
                  )

        assert_that(output, AssertMatchers.
                    validate_recidivism_metric(expected_recidivism_rate))

        test_pipeline.run()

    def testProduceReincarcerationRecidivismMetric_EmptyGroup(self):
        """Tests the ProduceRecivismMetric DoFn in the pipeline when there is
        no group associated with the metric.

        This should not happen in the pipeline, but we test against it
        anyways."""

        with pytest.raises(ValueError) as e:
            metric_key = {'stay_length': '36-48', 'gender': Gender.MALE,
                          'release_cohort': 2014,
                          'methodology': RecidivismMethodologyType.PERSON,
                          'follow_up_period': 1}

            release_group = []

            test_pipeline = TestPipeline()

            _ = (test_pipeline
                 | beam.Create([(metric_key, release_group)])
                 | 'Produce Recidivism Metric' >>
                 beam.ParDo(pipeline.ProduceReincarcerationRecidivismMetric())
                 )

            test_pipeline.run()

        assert str(e.value) == "The release_group is empty. " \
                               "[while running 'Produce Recidivism Metric']"

    def testProduceReincarcerationRecidivismMetric_EmptyMetric(self):
        """Tests the ProduceRecivismMetric DoFn in the pipeline when there is
        no group associated with the metric.

        This should not happen in the pipeline, but we test against it
        anyways."""

        with pytest.raises(ValueError) as e:

            metric_key = {}

            release_group = [0, 0, 0, 1, 0, 0, 0, 0, 1, 0]

            test_pipeline = TestPipeline()

            _ = (test_pipeline
                 | beam.Create([(metric_key, release_group)])
                 | 'Produce Recidivism Metric' >>
                 beam.ParDo(pipeline.ProduceReincarcerationRecidivismMetric())
                 )

            test_pipeline.run()

        assert str(e.value) == "The metric_key is empty. " \
                               "[while running 'Produce Recidivism Metric']"


class TestFilterMetrics(unittest.TestCase):
    """Tests for the FilterMetrics DoFn in the pipeline."""

    def testFilterMetrics_ExcludeAllDimensions(self):
        """Tests the FilterMetrics DoFn when all metrics with specific
        dimensions should be filtered from the output."""

        dimensions_to_filter = ['age_bucket', 'race', 'ethnicity',
                                'release_facility',
                                'gender', 'stay_length_bucket']
        methodologies = [RecidivismMethodologyType.EVENT,
                         RecidivismMethodologyType.PERSON]
        release_count_min = 0

        filter_metrics_kwargs = {
            'dimensions_to_filter_out': dimensions_to_filter,
            'methodologies': methodologies,
            'release_count_min': release_count_min}

        test_pipeline = TestPipeline()

        output = (test_pipeline
                  | beam.Create(MetricGroup.get_list())
                  | 'Produce Recidivism Metric' >>
                  beam.ParDo(pipeline.FilterMetrics(),
                             **filter_metrics_kwargs))

        assert_that(output,
                    equal_to(
                        [MetricGroup.recidivism_metric_without_dimensions]))

        test_pipeline.run()

    def testFilterMetrics_IncludeAge(self):
        """Tests the FilterMetrics DoFn when metrics including an age
         dimension should be included in the output. All other dimensions
         should be filtered from the output."""

        dimensions_to_filter = ['gender', 'race', 'ethnicity',
                                'release_facility', 'stay_length_bucket']
        methodologies = [RecidivismMethodologyType.EVENT,
                         RecidivismMethodologyType.PERSON]
        release_count_min = 0

        filter_metrics_kwargs = {
            'dimensions_to_filter_out': dimensions_to_filter,
            'methodologies': methodologies,
            'release_count_min': release_count_min}

        test_pipeline = TestPipeline()
        output = (test_pipeline
                  | beam.Create(MetricGroup.get_list())
                  | 'Produce Recidivism Metric' >>
                  beam.ParDo(pipeline.FilterMetrics(),
                             **filter_metrics_kwargs))

        assert_that(output,
                    equal_to(
                        [MetricGroup.recidivism_metric_without_dimensions,
                         MetricGroup.recidivism_metric_with_age]))

        test_pipeline.run()

    def testFilterMetrics_IncludeGender(self):
        """Tests the FilterMetrics DoFn when metrics including a gender
         dimension should be included in the output. All other dimensions
         should be filtered from the output."""

        dimensions_to_filter = ['age_bucket', 'race', 'ethnicity',
                                'release_facility', 'stay_length_bucket']
        methodologies = [RecidivismMethodologyType.EVENT,
                         RecidivismMethodologyType.PERSON]
        release_count_min = 0

        filter_metrics_kwargs = {
            'dimensions_to_filter_out': dimensions_to_filter,
            'methodologies': methodologies,
            'release_count_min': release_count_min}

        test_pipeline = TestPipeline()
        output = (test_pipeline
                  | beam.Create(MetricGroup.get_list())
                  | 'Produce Recidivism Metric' >>
                  beam.ParDo(pipeline.FilterMetrics(),
                             **filter_metrics_kwargs))

        assert_that(output,
                    equal_to(
                        [MetricGroup.recidivism_metric_without_dimensions,
                         MetricGroup.recidivism_metric_with_gender]))

        test_pipeline.run()

    def testFilterMetrics_IncludeRace(self):
        """Tests the FilterMetrics DoFn when metrics including a race
         dimension should be included in the output. All other dimensions
         should be filtered from the output."""

        dimensions_to_filter = ['age_bucket', 'gender', 'ethnicity',
                                'release_facility', 'stay_length_bucket']
        methodologies = [RecidivismMethodologyType.EVENT,
                         RecidivismMethodologyType.PERSON]
        release_count_min = 0

        filter_metrics_kwargs = {
            'dimensions_to_filter_out': dimensions_to_filter,
            'methodologies': methodologies,
            'release_count_min': release_count_min}

        test_pipeline = TestPipeline()
        output = (test_pipeline
                  | beam.Create(MetricGroup.get_list())
                  | 'Produce Recidivism Metric' >>
                  beam.ParDo(pipeline.FilterMetrics(),
                             **filter_metrics_kwargs))

        assert_that(output,
                    equal_to(
                        [MetricGroup.recidivism_metric_without_dimensions,
                         MetricGroup.recidivism_metric_with_race]))

        test_pipeline.run()

    def testFilterMetrics_IncludeEthnicity(self):
        """Tests the FilterMetrics DoFn when metrics including an ethnicity
         dimension should be included in the output. All other dimensions
         should be filtered from the output."""

        dimensions_to_filter = ['age_bucket', 'gender', 'race',
                                'release_facility', 'stay_length_bucket']
        methodologies = [RecidivismMethodologyType.EVENT,
                         RecidivismMethodologyType.PERSON]
        release_count_min = 0

        filter_metrics_kwargs = {
            'dimensions_to_filter_out': dimensions_to_filter,
            'methodologies': methodologies,
            'release_count_min': release_count_min}

        test_pipeline = TestPipeline()
        output = (test_pipeline
                  | beam.Create(MetricGroup.get_list())
                  | 'Produce Recidivism Metric' >>
                  beam.ParDo(pipeline.FilterMetrics(),
                             **filter_metrics_kwargs))

        assert_that(output,
                    equal_to(
                        [MetricGroup.recidivism_metric_without_dimensions,
                         MetricGroup.recidivism_metric_with_ethnicity]))

        test_pipeline.run()

    def testFilterMetrics_IncludeReleaseFacility(self):
        """Tests the FilterMetrics DoFn when metrics including a release
         facility dimension should be included in the output. All other
         dimensions should be filtered from the output."""

        dimensions_to_filter = ['age_bucket', 'gender', 'race', 'ethnicity',
                                'stay_length_bucket']
        methodologies = [RecidivismMethodologyType.EVENT,
                         RecidivismMethodologyType.PERSON]
        release_count_min = 0

        filter_metrics_kwargs = {
            'dimensions_to_filter_out': dimensions_to_filter,
            'methodologies': methodologies,
            'release_count_min': release_count_min}

        test_pipeline = TestPipeline()

        output = (test_pipeline
                  | beam.Create(MetricGroup.get_list())
                  | 'Produce Recidivism Metric' >>
                  beam.ParDo(pipeline.FilterMetrics(),
                             **filter_metrics_kwargs))

        assert_that(output, equal_to([
            MetricGroup.recidivism_metric_without_dimensions,
            MetricGroup.recidivism_metric_with_release_facility]))

        test_pipeline.run()

    def testFilterMetrics_IncludeStayLength(self):
        """Tests the FilterMetrics DoFn when metrics including a stay
        length dimension should be included in the output. All other
        dimensions should be filtered from the output."""

        dimensions_to_filter = ['age_bucket', 'gender', 'race', 'ethnicity',
                                'release_facility']
        methodologies = [RecidivismMethodologyType.EVENT,
                         RecidivismMethodologyType.PERSON]
        release_count_min = 0

        filter_metrics_kwargs = {
            'dimensions_to_filter_out': dimensions_to_filter,
            'methodologies': methodologies,
            'release_count_min': release_count_min}

        test_pipeline = TestPipeline()

        output = (test_pipeline
                  | beam.Create(MetricGroup.get_list())
                  | 'Produce Recidivism Metric' >>
                  beam.ParDo(pipeline.FilterMetrics(),
                             **filter_metrics_kwargs))

        assert_that(output,
                    equal_to(
                        [MetricGroup.recidivism_metric_without_dimensions,
                         MetricGroup.recidivism_metric_with_stay_length]))

        test_pipeline.run()

    def testFilterMetrics_IncludeTwoDimensions(self):
        """Tests the FilterMetrics DoFn when metrics including a gender
         or a stay length dimension should be included in the output. All other
        dimensions should be filtered from the output."""

        dimensions_to_filter = ['age_bucket', 'race', 'ethnicity',
                                'release_facility']
        methodologies = [RecidivismMethodologyType.EVENT,
                         RecidivismMethodologyType.PERSON]
        release_count_min = 0

        filter_metrics_kwargs = {
            'dimensions_to_filter_out': dimensions_to_filter,
            'methodologies': methodologies,
            'release_count_min': release_count_min}

        test_pipeline = TestPipeline()
        output = (test_pipeline
                  | beam.Create(MetricGroup.get_list())
                  | 'Produce Recidivism Metric' >>
                  beam.ParDo(pipeline.FilterMetrics(),
                             **filter_metrics_kwargs))

        assert_that(output,
                    equal_to(
                        [MetricGroup.recidivism_metric_without_dimensions,
                         MetricGroup.recidivism_metric_with_gender,
                         MetricGroup.recidivism_metric_with_stay_length]))

        test_pipeline.run()


class MetricGroup:
    """Stores a set of metrics where every dimension is included for testing
    dimension filtering."""
    recidivism_metric_with_age = ReincarcerationRecidivismMetric(
        execution_id=12345, release_cohort=2015, follow_up_period=1,
        methodology=RecidivismMethodologyType.PERSON, age_bucket='25-29',
        total_releases=1000, recidivated_releases=900, recidivism_rate=0.9)

    recidivism_metric_with_gender = ReincarcerationRecidivismMetric(
        execution_id=12345, release_cohort=2015, follow_up_period=1,
        methodology=RecidivismMethodologyType.PERSON, gender=Gender.MALE,
        total_releases=1000, recidivated_releases=875, recidivism_rate=0.875)

    recidivism_metric_with_race = ReincarcerationRecidivismMetric(
        execution_id=12345, release_cohort=2015, follow_up_period=1,
        methodology=RecidivismMethodologyType.PERSON, race=Race.BLACK,
        total_releases=1000, recidivated_releases=875, recidivism_rate=0.875)

    recidivism_metric_with_ethnicity = ReincarcerationRecidivismMetric(
        execution_id=12345, release_cohort=2015, follow_up_period=1,
        methodology=RecidivismMethodologyType.PERSON,
        ethnicity=Ethnicity.HISPANIC, total_releases=1000,
        recidivated_releases=875, recidivism_rate=0.875)

    recidivism_metric_with_release_facility = ReincarcerationRecidivismMetric(
        execution_id=12345, release_cohort=2015, follow_up_period=1,
        methodology=RecidivismMethodologyType.PERSON, release_facility='Red',
        total_releases=1000, recidivated_releases=300, recidivism_rate=0.30)

    recidivism_metric_with_stay_length = ReincarcerationRecidivismMetric(
        execution_id=12345, release_cohort=2015, follow_up_period=1,
        methodology=RecidivismMethodologyType.PERSON,
        stay_length_bucket='12-24', total_releases=1000,
        recidivated_releases=300, recidivism_rate=0.30)

    recidivism_metric_without_dimensions = ReincarcerationRecidivismMetric(
        execution_id=12345, release_cohort=2015,
        follow_up_period=1, methodology=RecidivismMethodologyType.PERSON,
        total_releases=1500, recidivated_releases=1200, recidivism_rate=0.80)

    @staticmethod
    def get_list():
        return [MetricGroup.recidivism_metric_with_age,
                MetricGroup.recidivism_metric_with_gender,
                MetricGroup.recidivism_metric_with_race,
                MetricGroup.recidivism_metric_with_ethnicity,
                MetricGroup.recidivism_metric_with_release_facility,
                MetricGroup.recidivism_metric_with_stay_length,
                MetricGroup.recidivism_metric_without_dimensions]


class AssertMatchers:
    """Functions to be used by Apache Beam testing `assert_that` functions to
    validate pipeline outputs."""

    @staticmethod
    def validate_pipeline_test():

        def _validate_pipeline_test(output):

            for metric in output:
                if not isinstance(metric, ReincarcerationRecidivismMetric):
                    raise BeamAssertException(
                        'Failed assert. Output is not'
                        'of type'
                        ' ReincarcerationRecidivismMetric.')

        return _validate_pipeline_test

    @staticmethod
    def count_combinations(expected_combination_counts):
        """Asserts that the number of metric combinations matches the expected
        counts for each release cohort year."""
        def _count_combinations(output):
            actual_combination_counts = {}

            for year in expected_combination_counts.keys():
                actual_combination_counts[year] = 0

            for result in output:
                combination, _ = result

                release_cohort_year = combination['release_cohort']
                actual_combination_counts[release_cohort_year] = \
                    actual_combination_counts[release_cohort_year] + 1

            for year in expected_combination_counts:
                if expected_combination_counts[year] != \
                        actual_combination_counts[year]:
                    raise BeamAssertException('Failed assert. Count does not'
                                              'match expected value.')

        return _count_combinations

    @staticmethod
    def validate_recidivism_metric(expected_recidivism_rate):
        """Asserts that the recidivism rate on the
         ReincarcerationRecidivismMetric produced by the pipeline matches the
          expected recidivism rate."""
        def _validate_recidivism_metric(output):
            if len(output) != 1:
                raise BeamAssertException('Failed assert. Should be only one '
                                          'ReincarcerationRecidivismMetric'
                                          ' returned.')

            recidivism_metric = output[0]

            if recidivism_metric.recidivism_rate != expected_recidivism_rate:
                raise BeamAssertException('Failed assert. Recidivism rate does'
                                          'not match expected value.')

        return _validate_recidivism_metric
