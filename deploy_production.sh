#!/usr/bin/env bash
source ./recidiviz/tools/deploy_pipeline_from_yaml.sh

echo "Fetching all tags"
git fetch --all --tags --prune

echo "Checking out tag $1"
git checkout tags/$1 -b $1

echo "Starting deploy of cron.yaml"
gcloud app deploy cron.yaml --project=recidiviz-123

echo "Starting task queue initialization"
pipenv run python -m recidiviz.tools.initialize_google_cloud_task_queues --project_id recidiviz-123 --google_auth_token $(gcloud auth print-access-token)

echo "Deploying calculation pipelines to templates"
deploy_pipelines ./deploy_pipeline_to_template.sh recidiviz-123 recidiviz-123-dataflow-templates ./calculation_pipeline_templates.yaml

VERSION=$(echo $1 | tr '.' '-')
STAGING_IMAGE_URL=us.gcr.io/recidiviz-staging/appengine/default.$VERSION:latest
PROD_IMAGE_URL=us.gcr.io/recidiviz-123/appengine/default.$VERSION:latest

echo "Starting deploy of main app"
gcloud container images add-tag $STAGING_IMAGE_URL $PROD_IMAGE_URL
gcloud app deploy prod.yaml --project=recidiviz-123 --version=$VERSION --image-url=$PROD_IMAGE_URL
