# Recidiviz - a platform for tracking granular recidivism metrics in real time
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
"""Define views for combining scraper & state-reports & ITP."""
# pylint:disable=line-too-long

from recidiviz.calculator.bq.views.bqview import BigQueryView
from recidiviz.calculator.bq.views.stitch.incarceration_trends_stitch_subset import INCARCERATION_TRENDS_STITCH_SUBSET_VIEW
from recidiviz.calculator.bq.views.stitch.scraper_aggregated_stitch_subset import SCRAPER_AGGREGATED_STITCH_SUBSET_VIEW
from recidiviz.calculator.bq.views.stitch.state_aggregate_stitch_subset import STATE_AGGREGATE_STITCH_SUBSET_VIEW
from recidiviz.calculator.bq.views.view_config import VIEWS_DATASET
from recidiviz.utils import metadata

PROJECT_ID: str = metadata.project_id()

_DESCRIPTION = """
Combine {interpolated_state_aggregate}, {scraper_data_aggregated},
{incarceration_trends_aggregate} into one unified view
""".format(interpolated_state_aggregate=INCARCERATION_TRENDS_STITCH_SUBSET_VIEW.view_id,
           scraper_data_aggregated=SCRAPER_AGGREGATED_STITCH_SUBSET_VIEW.view_id,
           incarceration_trends_aggregate=STATE_AGGREGATE_STITCH_SUBSET_VIEW.view_id)

_QUERY = """
/*{description}*/

SELECT * FROM `{project_id}.{views_dataset}.{interpolated_state_aggregate}`
UNION ALL
SELECT * FROM `{project_id}.{views_dataset}.{scraper_data_aggregated}`
UNION ALL
SELECT * FROM `{project_id}.{views_dataset}.{incarceration_trends_aggregate}`
""".format(project_id=PROJECT_ID, views_dataset=VIEWS_DATASET,
           interpolated_state_aggregate=INCARCERATION_TRENDS_STITCH_SUBSET_VIEW.view_id,
           scraper_data_aggregated=SCRAPER_AGGREGATED_STITCH_SUBSET_VIEW.view_id,
           incarceration_trends_aggregate=STATE_AGGREGATE_STITCH_SUBSET_VIEW.view_id,
           description=_DESCRIPTION)

COMBINED_STITCH_VIEW = BigQueryView(
    view_id='combined_stitch',
    view_query=_QUERY
)

if __name__ == '__main__':
    print(COMBINED_STITCH_VIEW.view_query)