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

"""Tests for incarceration_period_utils.py."""

import unittest
from datetime import date

from recidiviz.calculator.pipeline.utils.incarceration_period_utils import \
    drop_placeholder_temporary_and_missing_status_periods, \
    validate_admission_data, validate_release_data, \
    prepare_incarceration_periods_for_calculations
from recidiviz.common.constants.state.state_incarceration_period import \
    StateIncarcerationPeriodStatus, StateIncarcerationFacilitySecurityLevel
from recidiviz.common.constants.state.state_incarceration_period import \
    StateIncarcerationPeriodAdmissionReason as AdmissionReason
from recidiviz.common.constants.state.state_incarceration_period import \
    StateIncarcerationPeriodReleaseReason as ReleaseReason
from recidiviz.persistence.entity.state.entities import \
    StateIncarcerationPeriod, StatePerson
from recidiviz.calculator.pipeline.utils import \
    incarceration_period_utils as utils


class TestDropPlaceholderTemporaryAndMissingStatusPeriods(unittest.TestCase):
    """Tests the drop_placeholder_temporary_and_missing_status_periods
    function."""

    def test_drop_placeholder_temporary_and_missing_status_periods_placeholder(self):
        incarceration_periods = [StateIncarcerationPeriod.new_with_defaults(
            status=StateIncarcerationPeriodStatus.PRESENT_WITHOUT_INFO,
            state_code='XX',
            person=[StatePerson.new_with_defaults()],
            incarceration_period_id=1)]

        validated_incarceration_periods = \
            drop_placeholder_temporary_and_missing_status_periods(
                incarceration_periods)

        self.assertEqual([], validated_incarceration_periods)

    def test_drop_placeholder_temporary_and_missing_status_periods_temporary(self):
        incarceration_periods = [StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 11, 20),
            admission_reason=AdmissionReason.TEMPORARY_CUSTODY,
            release_date=date(2010, 12, 4),
            release_reason=ReleaseReason.RELEASED_FROM_TEMPORARY_CUSTODY
        )]

        validated_incarceration_periods = \
            drop_placeholder_temporary_and_missing_status_periods(
                incarceration_periods)

        self.assertEqual([], validated_incarceration_periods)

    def test_drop_placeholder_temporary_and_missing_status_periods_multiple_temporary(self):
        temporary_custody_1 = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 11, 20),
            admission_reason=AdmissionReason.TEMPORARY_CUSTODY,
            release_date=date(2010, 12, 4),
            release_reason=ReleaseReason.RELEASED_FROM_TEMPORARY_CUSTODY
        )

        temporary_custody_2 = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=112,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 12, 20),
            admission_reason=AdmissionReason.TEMPORARY_CUSTODY,
            release_date=date(2008, 12, 24),
            release_reason=ReleaseReason.RELEASED_FROM_TEMPORARY_CUSTODY
        )

        incarceration_periods = [temporary_custody_1, temporary_custody_2]

        validated_incarceration_periods = \
            drop_placeholder_temporary_and_missing_status_periods(
                incarceration_periods)

        self.assertEqual([], validated_incarceration_periods)

    def test_drop_placeholder_temporary_and_missing_status_periods_no_status(
            self):
        incarceration_periods = [StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=111,
            state_code='TX',
            admission_date=date(2008, 11, 20),
            admission_reason=AdmissionReason.NEW_ADMISSION,
            release_date=date(2010, 12, 4),
            release_reason=ReleaseReason.SENTENCE_SERVED
        )]

        validated_incarceration_periods = \
            drop_placeholder_temporary_and_missing_status_periods(
                incarceration_periods)

        self.assertEqual([], validated_incarceration_periods)

    def test_drop_placeholder_temporary_and_missing_status_periods_some_valid(
            self):
        temporary_custody = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 11, 20),
            admission_reason=AdmissionReason.TEMPORARY_CUSTODY,
            release_date=date(2010, 12, 4),
            release_reason=ReleaseReason.RELEASED_FROM_TEMPORARY_CUSTODY
        )

        valid_incarceration_period = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=1111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2016, 11, 20),
            admission_reason=AdmissionReason.NEW_ADMISSION,
            release_date=date(2017, 12, 4),
            release_reason=ReleaseReason.SENTENCE_SERVED)

        incarceration_periods = [temporary_custody, valid_incarceration_period]

        validated_incarceration_periods = \
            drop_placeholder_temporary_and_missing_status_periods(
                incarceration_periods)

        self.assertEqual([valid_incarceration_period],
                         validated_incarceration_periods)


class TestValidateAdmissionData(unittest.TestCase):
    """Tests the validate_admission_data function."""

    def test_validate_admission_data_empty_admission_date(self):
        first_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2008, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        input_incarceration_periods = [first_incarceration_period]

        valid_incarceration_periods = validate_admission_data(
            input_incarceration_periods
        )

        self.assertEqual([], valid_incarceration_periods)

    def test_validate_admission_data_empty_admission_reason(self):
        first_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2006, 1, 7),
                release_date=date(2008, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        input_incarceration_periods = [first_incarceration_period]

        valid_incarceration_periods = validate_admission_data(
            input_incarceration_periods
        )

        self.assertEqual([], valid_incarceration_periods)

    def test_validate_admission_data_empty_admission_data(self):
        first_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=None,
                admission_reason=None,
                release_date=date(2008, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        input_incarceration_periods = [first_incarceration_period]

        valid_incarceration_periods = validate_admission_data(
            input_incarceration_periods
        )

        self.assertEqual([], valid_incarceration_periods)


class TestValidateReleaseData(unittest.TestCase):
    """Tests the validate_release_data function."""

    def test_validate_release_data_empty_release_date(self):
        input_incarceration_periods = [
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=3333,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2012, 2, 4),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_reason=ReleaseReason.SENTENCE_SERVED)
        ]

        valid_incarceration_periods = validate_release_data(
            input_incarceration_periods
        )

        self.assertEqual([], valid_incarceration_periods)

    def test_validate_release_data_empty_release_reason(self):
        input_incarceration_periods = [
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=3333,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2012, 2, 4),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2014, 4, 14))
        ]

        valid_incarceration_periods = validate_release_data(
            input_incarceration_periods
        )

        self.assertEqual([], valid_incarceration_periods)

    def test_validate_release_data_empty_release_in_custody(self):
        initial_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 12, 4),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        first_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2011, 3, 4),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2014, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        second_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=3333,
                status=StateIncarcerationPeriodStatus.IN_CUSTODY,
                state_code='TX',
                admission_date=date(2012, 2, 4),
                admission_reason=AdmissionReason.NEW_ADMISSION)

        input_incarceration_periods = [
            initial_incarceration_period, first_reincarceration_period,
            second_reincarceration_period]

        valid_incarceration_periods = validate_release_data(
            input_incarceration_periods
        )

        self.assertEqual(input_incarceration_periods,
                         valid_incarceration_periods)

    def test_validate_release_data_released_in_future(self):
        not_actually_released = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 11, 20),
            admission_reason=AdmissionReason.NEW_ADMISSION,
            release_date=date(9999, 9, 9),
            release_reason=ReleaseReason.SENTENCE_SERVED
        )

        valid_incarceration_period = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=111,
            status=StateIncarcerationPeriodStatus.IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 11, 20),
            admission_reason=AdmissionReason.NEW_ADMISSION,
            release_date=None,
            release_reason=None
        )

        input_incarceration_periods = [not_actually_released]

        valid_incarceration_periods = validate_release_data(
            input_incarceration_periods
        )

        self.assertEqual([valid_incarceration_period],
                         valid_incarceration_periods)


class TestCollapseIncarcerationPeriods(unittest.TestCase):
    """Tests the collapse_incarceration_periods function."""

    def test_collapse_incarceration_periods(self):
        """Tests collapse_incarceration_periods for two incarceration
        periods linked by a transfer."""

        initial_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 12, 4),
                release_reason=ReleaseReason.TRANSFER)

        first_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2010, 12, 4),
                admission_reason=AdmissionReason.TRANSFER,
                release_date=date(2014, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        incarceration_periods = [initial_incarceration_period,
                                 first_reincarceration_period]

        collapsed_incarceration_periods = \
            utils.collapse_incarceration_periods(incarceration_periods)

        assert len(collapsed_incarceration_periods) == 1

        assert collapsed_incarceration_periods == [
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=initial_incarceration_period.
                incarceration_period_id,
                status=first_reincarceration_period.status,
                state_code=initial_incarceration_period.state_code,
                admission_date=initial_incarceration_period.admission_date,
                admission_reason=initial_incarceration_period.admission_reason,
                release_date=first_reincarceration_period.release_date,
                release_reason=first_reincarceration_period.release_reason)
        ]

    def test_collapse_incarceration_periods_no_transfers(self):
        """Tests collapse_incarceration_periods for two incarceration
        periods not linked by a transfer."""

        initial_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 12, 4),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        first_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2010, 12, 4),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2014, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        incarceration_periods = [initial_incarceration_period,
                                 first_reincarceration_period]

        collapsed_incarceration_periods = \
            utils.collapse_incarceration_periods(incarceration_periods)

        assert len(collapsed_incarceration_periods) == 2

        assert collapsed_incarceration_periods == incarceration_periods

    def test_collapse_incarceration_periods_multiple_transfers(self):
        """Tests collapse_incarceration_periods for a person who was repeatedly
        transferred between facilities. All of these incarceration periods
        should collapse into a single incarceration period."""

        initial_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 12, 4),
                release_reason=ReleaseReason.TRANSFER)

        first_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2011, 3, 2),
                admission_reason=AdmissionReason.TRANSFER,
                release_date=date(2012, 12, 4),
                release_reason=ReleaseReason.TRANSFER)

        second_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=3333,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2012, 2, 4),
                admission_reason=AdmissionReason.TRANSFER,
                release_date=date(2014, 4, 14),
                release_reason=ReleaseReason.TRANSFER)

        third_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=4444,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2016, 6, 2),
                admission_reason=AdmissionReason.TRANSFER,
                release_date=date(2017, 3, 1),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        incarceration_periods = [initial_incarceration_period,
                                 first_reincarceration_period,
                                 second_reincarceration_period,
                                 third_reincarceration_period]

        collapsed_incarceration_periods = \
            utils.collapse_incarceration_periods(incarceration_periods)

        assert len(collapsed_incarceration_periods) == 1

        assert collapsed_incarceration_periods == [
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=initial_incarceration_period.
                incarceration_period_id,
                status=third_reincarceration_period.status,
                state_code=initial_incarceration_period.state_code,
                admission_date=initial_incarceration_period.admission_date,
                admission_reason=initial_incarceration_period.admission_reason,
                release_date=third_reincarceration_period.release_date,
                release_reason=third_reincarceration_period.release_reason),
        ]

    def test_collapse_incarceration_periods_between_periods(self):
        """Tests collapse_incarceration_periods for two incarceration
        periods linked by a transfer preceded and followed by regular
        incarceration periods."""

        initial_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 12, 4),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        first_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2011, 3, 2),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2012, 12, 4),
                release_reason=ReleaseReason.TRANSFER)

        second_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=3333,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2012, 2, 4),
                admission_reason=AdmissionReason.TRANSFER,
                release_date=date(2014, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        third_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=4444,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2016, 6, 2),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2017, 3, 1),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        incarceration_periods = [initial_incarceration_period,
                                 first_reincarceration_period,
                                 second_reincarceration_period,
                                 third_reincarceration_period]

        collapsed_incarceration_periods = \
            utils.collapse_incarceration_periods(incarceration_periods)

        assert len(collapsed_incarceration_periods) == 3

        assert collapsed_incarceration_periods == [
            initial_incarceration_period,
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=first_reincarceration_period.
                incarceration_period_id,
                status=second_reincarceration_period.status,
                state_code=first_reincarceration_period.state_code,
                admission_date=first_reincarceration_period.admission_date,
                admission_reason=first_reincarceration_period.admission_reason,
                release_date=second_reincarceration_period.release_date,
                release_reason=second_reincarceration_period.release_reason),
            third_reincarceration_period
        ]

    def test_collapse_incarceration_periods_no_incarcerations(self):
        """Tests collapse_incarceration_periods for an empty list of
        incarceration periods."""

        collapsed_incarceration_periods = \
            utils.collapse_incarceration_periods([])

        assert not collapsed_incarceration_periods

    def test_collapse_incarceration_periods_one_incarceration(self):
        """Tests collapse_incarceration_periods for a person with only
        one incarceration period that ended with a sentence served."""

        only_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 12, 4),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        incarceration_periods = [only_incarceration_period]

        collapsed_incarceration_periods = \
            utils.collapse_incarceration_periods(incarceration_periods)

        assert collapsed_incarceration_periods == incarceration_periods

    def test_collapse_incarceration_periods_one_incarceration_transferred(self):
        """Tests collapse_incarceration_periods for a person with only
        one incarceration period that ended with a transfer out of state
        prison."""

        only_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 12, 4),
                release_reason=ReleaseReason.TRANSFER)

        incarceration_periods = [only_incarceration_period]

        collapsed_incarceration_periods = \
            utils.collapse_incarceration_periods(incarceration_periods)

        assert collapsed_incarceration_periods == incarceration_periods

    def test_collapse_incarceration_periods_transfer_out_then_in(self):
        """Tests collapse_incarceration_periods for a person who was
        transferred elsewhere, potentially out of state, and then reappeared
        in the state later as a new admission. These two periods should not
        be collapsed, because it's possible that this person was transferred
        to another state or to a federal prison, was completely released from
        that facility, and then has a new crime admission back into this state's
        facility.

        Then, this person was conditionally released, and returned later due to
        a transfer. These two period should also not be collapsed, because we
        don't have enough knowledge to make a safe assumption that this last
        incarceration period is connected to any of the previous ones.
        """

        initial_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 12, 4),
                release_reason=ReleaseReason.TRANSFER)

        first_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2011, 3, 2),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2012, 12, 4),
                release_reason=ReleaseReason.CONDITIONAL_RELEASE)

        second_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=3333,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2013, 12, 4),
                admission_reason=AdmissionReason.TRANSFER,
                release_date=date(2014, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        incarceration_periods = [initial_incarceration_period,
                                 first_reincarceration_period,
                                 second_reincarceration_period]

        collapsed_incarceration_periods = \
            utils.collapse_incarceration_periods(incarceration_periods)

        assert len(collapsed_incarceration_periods) == 3

        assert collapsed_incarceration_periods == incarceration_periods

    def test_collapse_incarceration_periods_transfer_back_then_transfer(self):
        """Tests collapse_incarceration_periods for a person who was transferred
        elsewhere, perhaps out of state, and then later reappears in the
        system as a new admission. These two incarceration periods should not
        be collapsed, because it's possible that this person was transferred
        to another state or to a federal prison, was completely released from
        that facility, and then has a new crime admission back into this state's
        facility.

        Then, this person was transferred out of this period and into a new
        incarceration period. These two periods should be collapsed because
        they are connected by a transfer.
        """

        initial_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 12, 4),
                release_reason=ReleaseReason.TRANSFER)

        first_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2011, 3, 2),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2012, 12, 4),
                release_reason=ReleaseReason.TRANSFER)

        second_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=3333,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2012, 12, 4),
                admission_reason=AdmissionReason.TRANSFER,
                release_date=date(2014, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        incarceration_periods = [initial_incarceration_period,
                                 first_reincarceration_period,
                                 second_reincarceration_period]

        collapsed_incarceration_periods = \
            utils.collapse_incarceration_periods(incarceration_periods)

        assert len(collapsed_incarceration_periods) == 2

        assert collapsed_incarceration_periods == [
            initial_incarceration_period,
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=first_reincarceration_period.
                incarceration_period_id,
                status=second_reincarceration_period.status,
                state_code=first_reincarceration_period.state_code,
                admission_date=first_reincarceration_period.admission_date,
                admission_reason=first_reincarceration_period.admission_reason,
                release_date=second_reincarceration_period.release_date,
                release_reason=second_reincarceration_period.release_reason),
        ]


class TestCombineIncarcerationPeriods(unittest.TestCase):
    """Tests for combine_incarceration_periods function."""

    def test_combine_incarceration_periods(self):
        """Tests for combining two incarceration periods connected by a
        transfer."""

        start_incarceration_period = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=1111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            facility='Green',
            housing_unit='House19',
            facility_security_level=StateIncarcerationFacilitySecurityLevel.
            MEDIUM,
            projected_release_reason=ReleaseReason.CONDITIONAL_RELEASE,
            admission_date=date(2008, 11, 20),
            admission_reason=AdmissionReason.NEW_ADMISSION,
            release_date=date(2010, 12, 4),
            release_reason=ReleaseReason.TRANSFER)

        end_incarceration_period = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=2222,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            facility='Jones',
            housing_unit='HouseUnit3',
            facility_security_level=StateIncarcerationFacilitySecurityLevel.
            MAXIMUM,
            projected_release_reason=ReleaseReason.SENTENCE_SERVED,
            admission_date=date(2010, 12, 4),
            admission_reason=AdmissionReason.TRANSFER,
            release_date=date(2012, 12, 10),
            release_reason=ReleaseReason.CONDITIONAL_RELEASE)

        combined_incarceration_period = \
            utils.combine_incarceration_periods(
                start_incarceration_period, end_incarceration_period
            )

        assert combined_incarceration_period == \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=start_incarceration_period.
                incarceration_period_id,
                status=end_incarceration_period.status,
                state_code=start_incarceration_period.state_code,
                facility=end_incarceration_period.facility,
                housing_unit=end_incarceration_period.housing_unit,
                facility_security_level=end_incarceration_period.
                facility_security_level,
                projected_release_reason=end_incarceration_period.
                projected_release_reason,
                admission_date=start_incarceration_period.admission_date,
                admission_reason=start_incarceration_period.admission_reason,
                release_date=end_incarceration_period.release_date,
                release_reason=end_incarceration_period.release_reason

            )


class TestPrepareIncarcerationPeriodsForCalculations(unittest.TestCase):
    """Tests the prepare_incarceration_periods_for_calculations function."""

    def test_prepare_incarceration_periods_for_calculations(self):
        initial_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 12, 4),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        first_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2011, 3, 4),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2014, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        second_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=3333,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2012, 2, 4),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2014, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        input_incarceration_periods = [
            initial_incarceration_period, first_reincarceration_period,
            second_reincarceration_period]

        validated_incarceration_periods = \
            prepare_incarceration_periods_for_calculations(
                input_incarceration_periods)

        self.assertEqual(validated_incarceration_periods,
                         input_incarceration_periods)

    def test_prepare_incarceration_periods_for_calculations_empty_admission_data_us_nd(self):
        """Tests that the incarceration periods are correctly collapsed when
        there's an empty admission_date and admission_reason following a
        transfer out, where the incarceration periods are from 'US_ND'.
        """
        first_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                external_id='99983-1|99983-2',
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='US_ND',
                admission_date=date(2004, 1, 3),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2008, 4, 14),
                release_reason=ReleaseReason.TRANSFER)

        second_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                external_id='99983-3',
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='US_ND',
                admission_date=None,
                admission_reason=None,
                release_date=date(2010, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        input_incarceration_periods = [first_incarceration_period,
                                       second_incarceration_period]

        collapsed_incarceration_periods = \
            prepare_incarceration_periods_for_calculations(
                input_incarceration_periods)

        self.assertEqual(collapsed_incarceration_periods, [
            StateIncarcerationPeriod.new_with_defaults(
                external_id='99983-1|99983-2',
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='US_ND',
                admission_date=date(2004, 1, 3),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)
        ])

    def test_prepare_incarceration_periods_for_calculations_empty_admission_data_not_us_nd(self):
        """Tests that the validator does not call the state-specific code to
        set empty admission data when the state code is not 'US_ND'.
        """
        first_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                external_id='99983-1|99983-2',
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='US_CA',
                admission_date=date(2004, 1, 3),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2008, 4, 14),
                release_reason=ReleaseReason.TRANSFER)

        second_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                external_id='99983-3',
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='US_CA',
                admission_date=None,
                admission_reason=None,
                release_date=date(2010, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        input_incarceration_periods = [first_incarceration_period,
                                       second_incarceration_period]

        collapsed_incarceration_periods = \
            prepare_incarceration_periods_for_calculations(
                input_incarceration_periods)

        self.assertEqual([first_incarceration_period],
                         collapsed_incarceration_periods)

    def test_prepare_incarceration_periods_for_calculations_multiple_temporary_and_valid(self):
        temporary_custody_1 = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 11, 20),
            admission_reason=AdmissionReason.TEMPORARY_CUSTODY,
            release_date=date(2010, 12, 4),
            release_reason=ReleaseReason.RELEASED_FROM_TEMPORARY_CUSTODY
        )

        temporary_custody_2 = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=112,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 12, 20),
            admission_reason=AdmissionReason.TEMPORARY_CUSTODY,
            release_date=date(2008, 12, 24),
            release_reason=ReleaseReason.RELEASED_FROM_TEMPORARY_CUSTODY
        )

        valid_incarceration_period = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=1111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2016, 11, 20),
            admission_reason=AdmissionReason.NEW_ADMISSION,
            release_date=date(2017, 12, 4),
            release_reason=ReleaseReason.SENTENCE_SERVED)

        incarceration_periods = [temporary_custody_1,
                                 temporary_custody_2,
                                 valid_incarceration_period]

        validated_incarceration_periods = \
            prepare_incarceration_periods_for_calculations(
                incarceration_periods)

        self.assertEqual(validated_incarceration_periods,
                         [valid_incarceration_period])

    def test_prepare_incarceration_periods_for_calculations_multiple_temporary_and_transfer(self):
        temporary_custody_1 = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 11, 20),
            admission_reason=AdmissionReason.TEMPORARY_CUSTODY,
            release_date=date(2010, 12, 4),
            release_reason=ReleaseReason.RELEASED_FROM_TEMPORARY_CUSTODY
        )

        temporary_custody_2 = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=112,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 12, 20),
            admission_reason=AdmissionReason.TEMPORARY_CUSTODY,
            release_date=date(2008, 12, 24),
            release_reason=ReleaseReason.RELEASED_FROM_TEMPORARY_CUSTODY
        )

        valid_incarceration_period_1 = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2011, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2012, 12, 4),
                release_reason=ReleaseReason.TRANSFER)

        valid_incarceration_period_2 = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1112,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2012, 12, 4),
                admission_reason=AdmissionReason.TRANSFER,
                release_date=date(2012, 12, 24),
                release_reason=ReleaseReason.TRANSFER)

        valid_incarceration_period_3 = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1113,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2012, 12, 24),
                admission_reason=AdmissionReason.TRANSFER,
                release_date=date(2012, 12, 30),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        incarceration_periods = [temporary_custody_1,
                                 temporary_custody_2,
                                 valid_incarceration_period_1,
                                 valid_incarceration_period_2,
                                 valid_incarceration_period_3]

        validated_incarceration_periods = \
            prepare_incarceration_periods_for_calculations(
                incarceration_periods)

        collapsed_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=valid_incarceration_period_1.
                incarceration_period_id,
                status=valid_incarceration_period_3.status,
                state_code=valid_incarceration_period_1.state_code,
                admission_date=valid_incarceration_period_1.admission_date,
                admission_reason=valid_incarceration_period_1.admission_reason,
                release_date=valid_incarceration_period_3.release_date,
                release_reason=valid_incarceration_period_3.release_reason
            )

        self.assertEqual(validated_incarceration_periods,
                         [collapsed_incarceration_period])

    def test_prepare_incarceration_periods_for_calculations_valid_then_temporary(self):

        valid_incarceration_period = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=1111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2008, 11, 20),
            admission_reason=AdmissionReason.NEW_ADMISSION,
            release_date=date(2009, 12, 4),
            release_reason=ReleaseReason.SENTENCE_SERVED)

        temporary_custody = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2010, 1, 20),
            admission_reason=AdmissionReason.TEMPORARY_CUSTODY,
            release_date=date(2010, 1, 24),
            release_reason=ReleaseReason.RELEASED_FROM_TEMPORARY_CUSTODY
        )

        incarceration_periods = [valid_incarceration_period, temporary_custody]

        validated_incarceration_periods = \
            prepare_incarceration_periods_for_calculations(
                incarceration_periods)

        self.assertEqual(validated_incarceration_periods,
                         [valid_incarceration_period])

    def test_prepare_incarceration_periods_for_calculations_temporary_between_valid(self):

        valid_incarceration_period_1 = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2009, 12, 4),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        temporary_custody = StateIncarcerationPeriod.new_with_defaults(
            incarceration_period_id=111,
            status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
            state_code='TX',
            admission_date=date(2010, 1, 20),
            admission_reason=AdmissionReason.TEMPORARY_CUSTODY,
            release_date=date(2010, 1, 24),
            release_reason=ReleaseReason.RELEASED_FROM_TEMPORARY_CUSTODY
        )

        valid_incarceration_period_2 = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=112,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2014, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2014, 12, 4),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        incarceration_periods = [valid_incarceration_period_1,
                                 temporary_custody,
                                 valid_incarceration_period_2]

        validated_incarceration_periods = \
            prepare_incarceration_periods_for_calculations(
                incarceration_periods)

        self.assertEqual(validated_incarceration_periods,
                         [valid_incarceration_period_1,
                          valid_incarceration_period_2])

    def test_sort_incarceration_periods(self):
        initial_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 12, 4),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        first_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2011, 3, 4),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2014, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        second_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=3333,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2012, 2, 4),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2014, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        input_incarceration_periods = [
            initial_incarceration_period, second_reincarceration_period,
            first_reincarceration_period]

        validated_incarceration_periods = \
            prepare_incarceration_periods_for_calculations(
                input_incarceration_periods)

        self.assertEqual(validated_incarceration_periods, [
            initial_incarceration_period,
            first_reincarceration_period,
            second_reincarceration_period])

    def test_collapse_incarceration_periods(self):
        initial_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 12, 4),
                release_reason=ReleaseReason.TRANSFER)

        first_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2010, 12, 4),
                admission_reason=AdmissionReason.TRANSFER,
                release_date=date(2014, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        incarceration_periods = [initial_incarceration_period,
                                 first_reincarceration_period]

        collapsed_incarceration_periods = \
            prepare_incarceration_periods_for_calculations(
                incarceration_periods)

        self.assertEqual(len(collapsed_incarceration_periods), 1)

        self.assertEqual(collapsed_incarceration_periods, [
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=initial_incarceration_period.
                incarceration_period_id,
                status=first_reincarceration_period.status,
                state_code=initial_incarceration_period.state_code,
                admission_date=initial_incarceration_period.admission_date,
                admission_reason=initial_incarceration_period.admission_reason,
                release_date=first_reincarceration_period.release_date,
                release_reason=first_reincarceration_period.release_reason)
        ])

    def test_collapse_incarceration_periods_missing_transfer_in(self):
        initial_incarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=1111,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2003, 1, 2),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2007, 4, 4),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        first_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=2222,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=date(2008, 11, 20),
                admission_reason=AdmissionReason.NEW_ADMISSION,
                release_date=date(2010, 12, 4),
                release_reason=ReleaseReason.TRANSFER)

        second_reincarceration_period = \
            StateIncarcerationPeriod.new_with_defaults(
                incarceration_period_id=3333,
                status=StateIncarcerationPeriodStatus.NOT_IN_CUSTODY,
                state_code='TX',
                admission_date=None,
                admission_reason=None,
                release_date=date(2014, 4, 14),
                release_reason=ReleaseReason.SENTENCE_SERVED)

        incarceration_periods = [initial_incarceration_period,
                                 first_reincarceration_period,
                                 second_reincarceration_period]

        collapsed_incarceration_periods = \
            prepare_incarceration_periods_for_calculations(
                incarceration_periods)

        self.assertEqual([initial_incarceration_period,
                          first_reincarceration_period],
                         collapsed_incarceration_periods)
