#!/bin/bash
# Test run script for APM Error Monitor

# Change to project root directory
cd /home/andrian/PodBay || exit 1

# Activate virtual environment
source /home/andrian/PodBay/venv/bin/activate

pip install -r /home/andrian/PodBay/requirements.txt

# Load configuration from config.properties (if it exists)
if [ -f /home/andrian/PodBay/k8s/config.properties ]; then
    export $(grep -v '^#' /home/andrian/PodBay/k8s/config.properties | grep -v '^$' | xargs)
else
    echo "Warning: config.properties not found, using environment variables or defaults"
fi

# Load secrets from secret.properties (if it exists)
if [ -f /home/andrian/PodBay/k8s/secret.properties ]; then
    export $(grep -v '^#' /home/andrian/PodBay/k8s/secret.properties | grep -v '^$' | xargs)
else
    echo "Warning: k8s/secret.properties not found, using environment variables or defaults"
fi

# Run the monitor script
echo "Running APM Error Monitor with configuration:"
echo "  ELASTICSEARCH_HOST: $ELASTICSEARCH_HOST"
echo "  SERVICE_NAME: ${SERVICE_NAME:-'(all services)'}"
echo "  ENVIRONMENT: ${ENVIRONMENT:-'(all environments)'}"
echo "  LOOKBACK_MINUTES: $LOOKBACK_MINUTES"
if [ "$JIRA_ENABLED" = "true" ]; then
    echo "  JIRA_ENABLED: true"
    echo "  JIRA_URL: ${JIRA_URL:-'(not set)'}"
    echo "  JIRA_EMAIL: ${JIRA_EMAIL:-'(not set)'}"
    echo "  JIRA_PROJECT_KEY: ${JIRA_PROJECT_KEY:-'(not set)'}"
    if [ -n "$JIRA_API_TOKEN" ]; then
        echo "  JIRA_API_TOKEN: $(echo "$JIRA_API_TOKEN")"
    else
        echo "  JIRA_API_TOKEN: (not set)"
    fi
fi
echo ""

python3 apm-error-monitor.py


