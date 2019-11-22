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
"""Revocation admissions in the last 60 days by county of supervision."""
# pylint: disable=line-too-long, trailing-whitespace

from recidiviz.calculator.query import export_config, bqview
from recidiviz.calculator.query.state import view_config
from recidiviz.utils import metadata

PROJECT_ID = metadata.project_id()
BASE_DATASET = export_config.STATE_BASE_TABLES_BQ_DATASET
VIEWS_DATASET = view_config.DASHBOARD_VIEWS_DATASET


REVOCATIONS_BY_COUNTY_60_DAYS_VIEW_NAME = 'revocations_by_county_60_days'

REVOCATIONS_BY_COUNTY_60_DAYS_DESCRIPTION = """
 Revocation admissions in the last 60 days by county, where the county
 is the county on the supervision period that was revoked.
 """

REVOCATIONS_BY_COUNTY_60_DAYS_QUERY = \
    """
    /*{description}*/
    
    SELECT state_code, county_code, count(*) as revocation_count FROM
    (SELECT sip.state_code, IFNULL(ssp.county_code, 'UNKNOWN_COUNTY') as county_code
    FROM
    `{project_id}.{views_dataset}.incarceration_admissions_by_person_60_days` sip
    LEFT JOIN `{project_id}.{base_dataset}.state_supervision_violation_response` resp
    ON resp.supervision_violation_response_id = sip.source_supervision_violation_response_id 
    LEFT JOIN `{project_id}.{base_dataset}.state_supervision_violation` viol
    ON viol.supervision_violation_id = resp.supervision_violation_id
    LEFT JOIN `{project_id}.{base_dataset}.state_supervision_period` ssp
    ON viol.supervision_period_id = ssp.supervision_period_id
    WHERE sip.admission_reason IN ('PAROLE_REVOCATION', 'PROBATION_REVOCATION')
    GROUP BY state_code, sip.person_id, county_code)
    GROUP BY state_code, county_code
    """.format(
        description=REVOCATIONS_BY_COUNTY_60_DAYS_DESCRIPTION,
        project_id=PROJECT_ID,
        views_dataset=VIEWS_DATASET,
        base_dataset=BASE_DATASET,
    )

REVOCATIONS_BY_COUNTY_60_DAYS_VIEW = bqview.BigQueryView(
    view_id=REVOCATIONS_BY_COUNTY_60_DAYS_VIEW_NAME,
    view_query=REVOCATIONS_BY_COUNTY_60_DAYS_QUERY
)

if __name__ == '__main__':
    print(REVOCATIONS_BY_COUNTY_60_DAYS_VIEW.view_id)
    print(REVOCATIONS_BY_COUNTY_60_DAYS_VIEW.view_query)