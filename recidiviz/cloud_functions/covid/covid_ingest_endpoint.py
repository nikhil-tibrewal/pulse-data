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

"""App Engine endpoint that calls Cloud Function for executing COVID ingest.

This endpoint exists to allow the COVID ingest Cloud Function to be triggered by
a cron task and/or manual triggering via a browser call.
"""

from http import HTTPStatus
import logging

import flask

from recidiviz.utils import metadata
from recidiviz.utils.auth import authenticate_request
from recidiviz.cloud_functions import cloud_function_utils


covid_blueprint = flask.Blueprint('covid', __name__)


_CLOUD_FUNCTION_URL = 'https://us-central1-{project_id}.cloudfunctions.net/execute-covid-aggregation' # pylint:disable=line-too-long
_RESPONSE_BODY = \
    'COVID ingest request sent. See Cloud Function logs for futher details.'


@covid_blueprint.route('/execute_covid_aggregation')
@authenticate_request
def execute_covid_aggregation():
    logging.info('COVID ingest endpoint triggered')

    project_id = metadata.project_id()
    if not project_id:
        logging.error('COVID ingest request failed due to missing project ID')
        return ('Could not send COVID ingest request due to missing project ID',
                HTTPStatus.INTERNAL_SERVER_ERROR)

    response = None
    try:
        response = cloud_function_utils.make_iap_request(
            _CLOUD_FUNCTION_URL.format(project_id=project_id),
            cloud_function_utils.IAP_CLIENT_ID[project_id])
    except Exception as e:
        logging.error('COVID ingest request failed with: %s', str(e))
        return str(e), HTTPStatus.INTERNAL_SERVER_ERROR

    logging.info(
        'COVID ingest request succeeded with response content: %s',
        response.text)
    return _RESPONSE_BODY, HTTPStatus.OK
