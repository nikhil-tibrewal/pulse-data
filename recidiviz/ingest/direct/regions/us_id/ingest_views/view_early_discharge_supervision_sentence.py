# Recidiviz - a data platform for criminal justice reform
# Copyright (C) 2020 Recidiviz, Inc.
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
"""Query for early discharges of supervision sentences."""
from recidiviz.ingest.direct.controllers.direct_ingest_big_query_view_types import \
    DirectIngestPreProcessedIngestViewBuilder
from recidiviz.ingest.direct.regions.us_id.ingest_views.templates_early_discharge import \
    early_discharge_view_template, EarlyDischargeType
from recidiviz.utils.environment import GAE_PROJECT_STAGING
from recidiviz.utils.metadata import local_project_id_override

VIEW_QUERY_TEMPLATE = early_discharge_view_template(discharge_type=EarlyDischargeType.SUPERVISION)

VIEW_BUILDER = DirectIngestPreProcessedIngestViewBuilder(
    region='us_id',
    ingest_view_name='early_discharge_supervision_sentence',
    view_query_template=VIEW_QUERY_TEMPLATE,
)

if __name__ == '__main__':
    with local_project_id_override(GAE_PROJECT_STAGING):
        VIEW_BUILDER.build_and_print()
