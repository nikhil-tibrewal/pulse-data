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
"""Tests for schema.py."""

from unittest import TestCase

from recidiviz.persistence.database.schema import (
    Arrest, ArrestHistory,
    Bond, BondHistory,
    Booking, BookingHistory,
    Charge, ChargeHistory,
    Hold, HoldHistory,
    Person, PersonHistory,
    Sentence, SentenceHistory,
    SentenceRelationship, SentenceRelationshipHistory)


class SchemaTest(TestCase):
    """Test matching columns in master and historical tables for each entity"""


    def testMasterAndHistoryColumnsMatch_Arrest(self):
        self._assert_columns_match(Arrest,
                                   ArrestHistory,
                                   table_b_exclusions=[
                                       'arrest_history_id',
                                       'valid_from',
                                       'valid_to'])


    def testMasterAndHistoryColumnsMatch_Bond(self):
        self._assert_columns_match(Bond,
                                   BondHistory,
                                   table_b_exclusions=[
                                       'bond_history_id',
                                       'valid_from',
                                       'valid_to'])


    def testMasterAndHistoryColumnsMatch_Booking(self):
        self._assert_columns_match(Booking,
                                   BookingHistory,
                                   table_a_exclusions=['last_seen_time'],
                                   table_b_exclusions=[
                                       'booking_history_id',
                                       'valid_from',
                                       'valid_to'])


    def testMasterAndHistoryColumnsMatch_Charge(self):
        self._assert_columns_match(Charge,
                                   ChargeHistory,
                                   table_b_exclusions=[
                                       'charge_history_id',
                                       'valid_from',
                                       'valid_to'])


    def testMasterAndHistoryColumnsMatch_Hold(self):
        self._assert_columns_match(Hold,
                                   HoldHistory,
                                   table_b_exclusions=[
                                       'hold_history_id',
                                       'valid_from',
                                       'valid_to'])


    def testMasterAndHistoryColumnsMatch_Person(self):
        self._assert_columns_match(Person,
                                   PersonHistory,
                                   table_a_exclusions=[
                                       'surname',
                                       'given_names',
                                       'birthdate',
                                       'birthdate_inferred_from_age'],
                                   table_b_exclusions=[
                                       'person_history_id',
                                       'valid_from',
                                       'valid_to'])


    def testMasterAndHistoryColumnsMatch_Sentence(self):
        self._assert_columns_match(Sentence,
                                   SentenceHistory,
                                   table_b_exclusions=[
                                       'sentence_history_id',
                                       'valid_from',
                                       'valid_to'])


    def testMasterAndHistoryColumnsMatch_SentenceRelationship(self):
        self._assert_columns_match(SentenceRelationship,
                                   SentenceRelationshipHistory,
                                   table_b_exclusions=[
                                       'sentence_relationship_history_id',
                                       'valid_from',
                                       'valid_to'])


    def _assert_columns_match(self, table_a, table_b, table_a_exclusions=None,
                              table_b_exclusions=None):
        """Asserts that each column in table_a has a corresponding column with
        the same name in table_b, and vice versa.

        Any column name included in a table's list of exclusions will be ignored
        in this comparison.
        """

        if table_a_exclusions is None:
            table_a_exclusions = []
        if table_b_exclusions is None:
            table_b_exclusions = []

        # Strip leading table name from column names
        table_a_column_names = {str(column).split('.')[1] for column in
                                table_a.__table__.columns}
        table_b_column_names = {str(column).split('.')[1] for column in
                                table_b.__table__.columns}

        # Remove all exclusions. This is done for each exclusion separately
        # rather than using a list comprehension so that an error can be thrown
        # if an exclusion is passed for a column that doesn't exist. (The
        # built-in exception for `remove` isn't used because it doesn't display
        # the missing value in the error message.)
        for exclusion in table_a_exclusions:
            if not exclusion in table_a_column_names:
                raise ValueError(
                    '{exclusion} is not a column in {table_name}'.format(
                        exclusion=exclusion, table_name=table_a.__name__))
            table_a_column_names.remove(exclusion)
        for exclusion in table_b_exclusions:
            if not exclusion in table_b_column_names:
                raise ValueError(
                    '{exclusion} is not a column in {table_name}'.format(
                        exclusion=exclusion, table_name=table_b.__name__))
            table_b_column_names.remove(exclusion)

        self.assertEqual(table_a_column_names, table_b_column_names)