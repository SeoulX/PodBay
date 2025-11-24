#!/bin/bash
# Test script that injects mock data and then runs the monitor

# Activate virtual environment
source /home/andrian/aadinnr_files/resume_env/bin/activate

# Load configuration from config.properties
export $(grep -v '^#' config.properties | grep -v '^$' | xargs)

# Load secrets from secret.properties
export $(grep -v '^#' secret.properties | grep -v '^$' | xargs)

echo "=========================================="
echo "Step 1: Injecting mock APM error data..."
echo "=========================================="
python3 inject-mock-data.py

echo ""
echo "=========================================="
echo "Step 2: Running APM Error Monitor..."
echo "=========================================="
python3 apm-error-monitor.py


