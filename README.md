# APM Error Monitor

This monitoring solution queries Elasticsearch for APM errors from the FastAPI application and sends alerts to a Slack webhook when errors are detected.

## Quick Start: Getting a Slack Webhook

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"** → **"From scratch"**
3. Name your app (e.g., "APM Error Monitor") and select your workspace
4. Click **"Incoming Webhooks"** → Toggle **"Activate Incoming Webhooks"** to **On**
5. Click **"Add New Webhook to Workspace"**
6. Select the channel for alerts (e.g., `#alerts`)
7. Copy the **Webhook URL** (format: `https://hooks.slack.com/services/T.../B.../...`)
8. Add it to `secret.properties` as `SLACK_WEBHOOK=your-webhook-url`

See detailed instructions in the [Setup](#setup) section below.

## Overview

The monitor queries Elasticsearch for APM errors from the FastAPI application and sends alerts to a Slack webhook when errors are detected.

**Deployment Options:**
- **CronJob** (recommended): Runs periodically every 5 minutes
- **Deployment**: Runs continuously, checking every 5 minutes

## Files

- `apm-error-monitor.py` - Main monitoring script (supports both one-time and continuous modes)
- `inject-mock-data.py` - Script to inject test APM error data into Elasticsearch
- `test-run.sh` - Test script to run the monitor locally
- `test-with-mock.sh` - Test script that injects mock data and runs the monitor
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container image definition
- `cronjob.yaml` - Kubernetes CronJob manifest (periodic execution)
- `deployment.yaml` - Kubernetes Deployment manifest (continuous monitoring)
- `kustomization.yaml` - Kustomize configuration
- `config.properties` - Configuration (non-sensitive)
- `secret.properties.template` - Template for secrets (copy to `secret.properties`)

## Configuration

### Environment Variables

- `ELASTICSEARCH_HOST` - Elasticsearch endpoint (default: `http://elasticsearch:9200`)
- `ELASTICSEARCH_USERNAME` - Elasticsearch username (optional, for authenticated clusters)
- `ELASTICSEARCH_PASSWORD` - Elasticsearch password (optional, for authenticated clusters)
- `SERVICE_NAME` - APM service name to monitor (optional: leave empty to monitor all services)
- `ENVIRONMENT` - Environment name to filter (optional: leave empty to monitor all environments)
- `LOOKBACK_MINUTES` - Time window to check for errors (default: `5`)
- `SLACK_WEBHOOK` - Slack webhook URL (required)
- `MONITOR_INTERVAL` - Optional: If set (in seconds), runs in continuous mode instead of one-time execution

### Setup

1. **Get a Slack Webhook URL:**
   
   **Option A: Using Slack Incoming Webhooks (Recommended)**
   
   a. Go to [https://api.slack.com/apps](https://api.slack.com/apps) and sign in
   
   b. Click **"Create New App"** → **"From scratch"**
   
   c. Give your app a name (e.g., "APM Error Monitor") and select your workspace
   
   d. Click **"Incoming Webhooks"** in the left sidebar
   
   e. Toggle **"Activate Incoming Webhooks"** to **On**
   
   f. Click **"Add New Webhook to Workspace"**
   
   g. Select the channel where you want to receive alerts (e.g., `#alerts`, `#monitoring`)
   
   h. Click **"Allow"**
   
   **Option B: Using Slack Workflow Builder (Simpler)**
   
   a. In Slack, go to your workspace settings
   
   b. Navigate to **Workflows** → **Create Workflow**
   
   c. Choose **"Webhook"** as the trigger
   
   d. Copy the webhook URL provided
   
   **Option C: Using Existing Slack App**
   
   If you already have a Slack app:
   - Go to [https://api.slack.com/apps](https://api.slack.com/apps)
   - Select your app
   - Navigate to **Incoming Webhooks**
   - Add a new webhook or use an existing one

2. **Configure credentials:**
   Copy the template and set your credentials:
   ```bash
   cp secret.properties.template secret.properties
   # Edit secret.properties and set:
   # - SLACK_WEBHOOK: Your Slack webhook URL (required)
   # - ELASTICSEARCH_USERNAME: Your Elasticsearch username (if required)
   # - ELASTICSEARCH_PASSWORD: Your Elasticsearch password (if required)
   ```
   Example `secret.properties`:
   ```
   ELASTICSEARCH_USERNAME=your-username
   ELASTICSEARCH_PASSWORD=your-password
   ```
   Note: `secret.properties` is gitignored to prevent committing sensitive data.

3. **Build the Docker image:**
   ```bash
   docker build -t apm-error-monitor:latest .
   # Or push to your registry:
   docker tag apm-error-monitor:latest your-registry/apm-error-monitor:latest
   docker push your-registry/apm-error-monitor:latest
   ```

4. **Update the image in manifests:**
   If using a registry, update the `image` field in `cronjob.yaml` and/or `deployment.yaml`:
   ```yaml
   image: your-registry/apm-error-monitor:latest
   ```

5. **Choose deployment method:**
   
   **Option A: CronJob (Recommended for periodic checks)**
   ```bash
   kubectl apply -k monitoring/
   ```
   This uses the CronJob which runs every 5 minutes.
   
   **Option B: Deployment (For continuous monitoring)**
   Edit `kustomization.yaml` to include `deployment.yaml` instead of `cronjob.yaml`:
   ```yaml
   resources:
   - deployment.yaml  # Change from cronjob.yaml
   ```
   Then deploy:
   ```bash
   kubectl apply -k monitoring/
   ```

## Monitoring

### For CronJob deployment:

**Check CronJob status:**
```bash
kubectl get cronjob -n elastic-stack apm-error-monitor
```

**View recent jobs:**
```bash
kubectl get jobs -n elastic-stack -l app=apm-error-monitor
```

**View logs:**
```bash
# Get the latest job pod
POD=$(kubectl get pods -n elastic-stack -l app=apm-error-monitor --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')

# View logs
kubectl logs -n elastic-stack $POD
```

**Manual execution:**
```bash
kubectl create job --from=cronjob/apm-error-monitor manual-check -n elastic-stack
```

### For Deployment:

**Check deployment status:**
```bash
kubectl get deployment -n elastic-stack apm-error-monitor
```

**View logs:**
```bash
kubectl logs -n elastic-stack -l app=apm-error-monitor -f
```

## Alert Payloads

### Individual Service/Environment Alerts

When errors are detected for a specific service/environment combination, individual alerts are sent:

```json
{
  "alert_type": "apm_error",
  "service": "fastapi-app",
  "actual_value": 5,
  "environment": "production",
  "fired_at": "2024-01-15T10:30:00.000Z"
}
```

### Summary Alert

A summary alert is also sent with all service/environment combinations:

```json
{
  "alert_type": "apm_error_summary",
  "total_errors": 15,
  "affected_services": 3,
  "errors_by_service_env": [
    {
      "service": "fastapi-app",
      "environment": "production",
      "error_count": 5
    },
    {
      "service": "fastapi-app",
      "environment": "staging",
      "error_count": 3
    },
    {
      "service": "web-service",
      "environment": "production",
      "error_count": 7
    }
  ],
  "fired_at": "2024-01-15T10:30:00.000Z"
}
```

## Customization

### Change schedule frequency:
Edit the `schedule` field in `cronjob.yaml`:
- Every 5 minutes: `*/5 * * * *`
- Every 10 minutes: `*/10 * * * *`
- Every hour: `0 * * * *`

### Monitor specific service or all services:
- To monitor all services: Leave `SERVICE_NAME` empty in `config.properties`
- To monitor a specific service: Set `SERVICE_NAME` to the service name

### Monitor specific environment or all environments:
- To monitor all environments: Leave `ENVIRONMENT` empty in `config.properties`
- To monitor a specific environment: Set `ENVIRONMENT` to the environment name

### Adjust lookback window:
Update `LOOKBACK_MINUTES` in `config.properties`.

## Troubleshooting

### No alerts received:
1. Check if the CronJob is running: `kubectl get cronjob -n elastic-stack`
2. Check job logs for errors
3. Verify Elasticsearch connectivity
4. Verify webhook URL is correct

### Connection errors:
- Ensure Elasticsearch service is accessible from the monitoring pod
- Check network policies if using them
- Verify the Elasticsearch host URL is correct

### Query errors:
- Verify APM indices exist: `curl http://elasticsearch:9200/_cat/indices/apm-*`
- Check if the service name matches the APM service name
- Verify APM data is being ingested

## Testing with Mock Data

To test the monitoring system with mock data:

1. **Inject mock APM error data:**
   ```bash
   cd phase3/k8s/elk-stack/monitoring
   source /home/andrian/aadinnr_files/resume_env/bin/activate
   export $(grep -v '^#' config.properties | grep -v '^$' | xargs)
   export $(grep -v '^#' secret.properties | grep -v '^$' | xargs)
   python3 inject-mock-data.py
   ```

2. **Or use the test script:**
   ```bash
   ./test-with-mock.sh
   ```

3. **Customize mock data:**
   ```bash
   # Inject 10 errors instead of default 5
   NUM_ERRORS=10 python3 inject-mock-data.py
   
   # Use custom services and environments
   SERVICES="my-service,another-service" ENVIRONMENTS="prod,staging" python3 inject-mock-data.py
   ```

The mock data script will:
- Inject errors across multiple services and environments
- Use timestamps within the last 5 minutes (configurable via `LOOKBACK_MINUTES`)
- Create realistic APM error documents that match the expected structure

After injecting mock data, run the monitor to see it detect and alert on the errors.

