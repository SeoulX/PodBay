# How to Run APM Error Monitor

## Prerequisites

1. **Python 3.6+** installed
2. **Virtual environment** (optional but recommended)
3. **Configuration files** set up

## Setup

### 1. Install Dependencies

```bash
# Option A: Using virtual environment (recommended)
source /home/andrian/aadinnr_files/resume_env/bin/activate
pip install -r requirements.txt

# Option B: Install globally
pip install -r requirements.txt
```

### 2. Configure Environment

Make sure you have:
- `config.properties` - Non-sensitive configuration
- `secret.properties` - Sensitive data (webhook URLs, passwords)

If `secret.properties` doesn't exist, copy from template:
```bash
cp secret.properties.template secret.properties
# Edit secret.properties and add your SLACK_WEBHOOK and credentials
```

## Running the Monitor

### Option 1: Using Test Scripts (Easiest)

**Run monitor only:**
```bash
./test-run.sh
```

**Inject mock data and run monitor:**
```bash
./test-with-mock.sh
```

### Option 2: Manual Run

**Load configuration and run:**
```bash
# Load config from properties files
export $(grep -v '^#' config.properties | grep -v '^$' | xargs)
export $(grep -v '^#' secret.properties | grep -v '^$' | xargs)

# Run the monitor
python3 apm-error-monitor.py
```

**Or set environment variables directly:**
```bash
export ELASTICSEARCH_HOST="http://es-v4.media-meter.in:80"
export ELASTICSEARCH_USERNAME="your-username"  # Optional
export ELASTICSEARCH_PASSWORD="your-password"  # Optional
export SLACK_WEBHOOK="https://hooks.slack.com/services/..."
export SERVICE_NAME=""  # Optional: leave empty for all services
export ENVIRONMENT=""   # Optional: leave empty for all environments
export LOOKBACK_MINUTES=5

python3 apm-error-monitor.py
```

## Running Modes

### One-Time Run (CronJob mode)
Runs once and exits. Perfect for Kubernetes CronJobs:
```bash
python3 apm-error-monitor.py
```

### Continuous Mode
Runs continuously, checking at specified intervals:
```bash
export MONITOR_INTERVAL=300  # Check every 300 seconds (5 minutes)
python3 apm-error-monitor.py
```

## Inject Mock Data

To test the monitoring system with mock data:

```bash
# Load configuration
export $(grep -v '^#' config.properties | grep -v '^$' | xargs)
export $(grep -v '^#' secret.properties | grep -v '^$' | xargs)

# Inject mock data
python3 inject-mock-data.py
```

**Customize mock data:**
```bash
# Inject 10 errors instead of default 5
NUM_ERRORS=10 python3 inject-mock-data.py

# Use custom services and environments
SERVICES="my-service,another-service" \
ENVIRONMENTS="prod,staging" \
python3 inject-mock-data.py
```

## Package Structure

The code is organized in the `apm_monitor` package:

```
apm_monitor/
├── config.py              # Configuration management
├── elasticsearch_client.py # ES client wrapper
├── queries.py              # Query logic
├── alerts.py               # Webhook alerts
├── monitor.py              # Main monitoring class
└── mock_data.py           # Mock data injection
```

Entry points:
- `apm-error-monitor.py` - Main monitoring script
- `inject-mock-data.py` - Mock data injector

## Troubleshooting

### Import Errors
If you get `ModuleNotFoundError: No module named 'apm_monitor'`:
- Make sure you're in the `/home/andrian/PodBay` directory
- The `apm_monitor` package should be in the same directory as the scripts

### Connection Errors
- Verify Elasticsearch host is accessible
- Check credentials in `secret.properties`
- Test connection: `curl $ELASTICSEARCH_HOST`

### Missing Dependencies
```bash
pip install -r requirements.txt
```

## Example Workflow

1. **Test with mock data:**
   ```bash
   ./test-with-mock.sh
   ```

2. **Run monitor once:**
   ```bash
   ./test-run.sh
   ```

3. **Run continuously:**
   ```bash
   export MONITOR_INTERVAL=300
   ./test-run.sh
   ```

