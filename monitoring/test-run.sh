#!/bin/bash
# Test run script for APM Error Monitor

# Activate virtual environment
source /home/andrian/aadinnr_files/resume_env/bin/activate

# Load configuration from config.properties
export $(grep -v '^#' config.properties | grep -v '^$' | xargs)

# Load secrets from secret.properties
export $(grep -v '^#' secret.properties | grep -v '^$' | xargs)

# Run the monitor script
echo "Running APM Error Monitor with configuration:"
echo "  ELASTICSEARCH_HOST: $ELASTICSEARCH_HOST"
echo "  SERVICE_NAME: ${SERVICE_NAME:-'(all services)'}"
echo "  ENVIRONMENT: ${ENVIRONMENT:-'(all environments)'}"
echo "  LOOKBACK_MINUTES: $LOOKBACK_MINUTES"
echo ""

python3 apm-error-monitor.py


