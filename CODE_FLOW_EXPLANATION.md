# APM Error Monitor - Code Flow Explanation

## Overview
The APM Error Monitor continuously checks Elasticsearch for application errors and sends alerts to Slack channels based on the service name.

---

## 1. Entry Point: `apm-error-monitor.py`

### Step 1: Configuration Loading
```python
def load_config_from_files()
```
- Reads `config.properties` and `secret.properties`
- Loads environment variables if not already set
- This allows running the script directly without shell environment setup

### Step 2: Main Execution
```python
monitor = APMErrorMonitor()
monitor.initialize()
```
- Creates the monitor instance
- Initializes all components

### Step 3: Run Mode Decision
- **If `MONITOR_INTERVAL` is set**: Runs continuously (checks every N seconds)
- **If not set**: Runs once and exits (for CronJob mode)

---

## 2. Configuration: `apm_monitor/config.py`

### Config Class Initialization
Reads environment variables and builds configuration:

1. **Elasticsearch Config**:
   - `ELASTICSEARCH_HOST` - Elasticsearch server URL
   - `ELASTICSEARCH_USERNAME` / `ELASTICSEARCH_PASSWORD` - Auth credentials

2. **Monitoring Config**:
   - `LOOKBACK_MINUTES` - How far back to search for errors (default: 5 minutes)
   - `MONITOR_INTERVAL` - Seconds between checks (optional, for continuous mode)
   - `SERVICE_NAME` - Filter by specific service (optional)
   - `ENVIRONMENT` - Filter by specific environment (optional)

3. **Webhook Config**:
   - `SLACK_WEBHOOK` - Default webhook URL
   - Individual service webhooks:
     - `SALINA_WEBHOOK` → Maps to Salina services
     - `MEDIA_METER_WEBHOOK` → Maps to Media-Meter Global API V2
     - `SCOUP_WEBHOOK` → Maps to Scoup API services
     - `BEBOT_WEBHOOK` → Maps to Bebot Fast API
     - `SEARCHSIFT_WEBHOOK` → Maps to Searchsift

4. **Service Webhook Mapping**:
   ```python
   service_webhook_mapping = {
       "Salina Auth API": "SALINA_WEBHOOK",
       "Media-Meter Global API V2": "MEDIA_METER_WEBHOOK",
       ...
   }
   ```
   - Maps service names to their webhook environment variables
   - Builds `service_webhooks` dictionary for quick lookup

---

## 3. Initialization: `apm_monitor/monitor.py`

### `initialize()` Method

1. **Validate Config**:
   - Checks if `SLACK_WEBHOOK` is set
   - Exits if validation fails

2. **Connect to Elasticsearch**:
   ```python
   self.es_client = ElasticsearchClient(self.config)
   self.es_client.check_connection()
   ```
   - Creates Elasticsearch client with auth
   - Tests connection to cluster

3. **Initialize Components**:
   ```python
   self.queries = APMErrorQueries(self.es_client.get_client())
   self.alerts = WebhookAlerts(self.config.slack_webhook, self.config.service_webhooks)
   ```
   - `APMErrorQueries` - Handles Elasticsearch queries
   - `WebhookAlerts` - Handles Slack webhook sending

---

## 4. Monitoring Loop: `run_check()` Method

### Step 1: Query Elasticsearch for Errors
```python
errors_by_service_env, total_errors = self.queries.query_errors_by_service_env(
    service_name, environment, lookback_minutes
)
```

**What happens in `queries.py`:**

1. **Build Query Filters**:
   ```python
   filters = [
       {"term": {"processor.event": "error"}},  # Only error events
       {"range": {"@timestamp": {"gte": "now-5m"}}}  # Last 5 minutes
   ]
   ```

2. **Add Optional Filters**:
   - Service name filter (if `SERVICE_NAME` is set)
   - Environment filter (if `ENVIRONMENT` is set)

3. **Build Aggregation Query**:
   ```json
   {
     "query": {...filters...},
     "size": 0,  // Don't return documents, just counts
     "aggs": {
       "by_service": {
         "terms": {"field": "service.name"},
         "aggs": {
           "by_environment": {
             "terms": {"field": "service.environment"},
             "aggs": {
               "sample_errors": {
                 "top_hits": {
                   "size": 3,  // Get 3 sample error documents
                   "_source": ["error.log.message", "error.culprit", "error.type"]
                 }
               }
             }
           }
         }
       }
     }
   }
   ```

4. **Execute Query**:
   - Queries `logs-apm.error*` indices
   - Returns aggregated results grouped by service and environment

5. **Parse Results**:
   ```python
   errors_by_service_env = [
       {
           "service": "Media-Meter Global API V2",
           "environment": "production",
           "error_count": 7,
           "sample_errors": [
               {
                   "message": "Error message...",
                   "type": "DuplicateKeyError",
                   "culprit": "app.core.services",
                   "timestamp": "2025-11-25T09:00:00"
               },
               ...
           ]
       },
       ...
   ]
   ```

### Step 2: Process Results

**If errors found (`total_errors > 0`):**

1. **Loop through each service/environment combination**:
   ```python
   for error_info in errors_by_service_env:
       if error_info["error_count"] > 0:
   ```

2. **Send Alert for Each**:
   ```python
   self.alerts.send_alert(
       service_name="Media-Meter Global API V2",
       error_count=7,
       environment="production",
       sample_errors=[...]
   )
   ```

**If no errors:**
- Logs "No errors detected" and continues

---

## 5. Alert Sending: `apm_monitor/alerts.py`

### `send_alert()` Method Flow

#### Step 1: Get Webhook URL for Service
```python
webhook_url = self.get_webhook_url_for_service(service_name)
```

**Matching Logic:**
1. **Exact Match**: Check if service name exists in `service_webhooks` dict
   - "Media-Meter Global API V2" → Found → Returns `MEDIA_METER_WEBHOOK` URL

2. **Partial Match**: If no exact match, check if any key contains the service name
   - "Salina Auth API Staging" → Matches "Salina Auth API" → Returns `SALINA_WEBHOOK` URL

3. **Default**: If no match → Returns `SLACK_WEBHOOK` (default)

#### Step 2: Build Alert Payload
```python
payload = {
    "text": "🚨 *APM Error Alert*\n\n*Service:* Media-Meter Global API V2\n...",
    "attachments": [{
        "color": "danger",
        "fields": [
            {"title": "Service", "value": "Media-Meter Global API V2"},
            {"title": "Environment", "value": "production"},
            {"title": "Error Count", "value": "7"},
            {"title": "Time", "value": "2025-11-25 09:00:00 PHT"},
            {
                "title": "Sample Errors",
                "value": "*Error 1:*\nType: DuplicateKeyError\nLocation: app.core\nMessage: ..."
            }
        ]
    }]
}
```

**Sample Errors Section:**
- Extracts up to 3 sample errors from the query results
- Shows: Error type, location (culprit), and message
- Truncates long messages to 300 characters for Slack

#### Step 3: Send to Slack
```python
response = requests.post(webhook_url, json=payload, timeout=10)
```

**Webhook Routing:**
- "Media-Meter Global API V2" → Uses `MEDIA_METER_WEBHOOK` → Posts to `#global-api-alerts`
- "Salina Auth API" → Uses `SALINA_WEBHOOK` → Posts to `#salina-alerts`
- Unknown service → Uses `SLACK_WEBHOOK` → Posts to default channel

#### Step 4: Error Handling
- Logs success or detailed error (HTTP status, response body)
- Returns `True` if successful, `False` if failed

---

## 6. Continuous Mode: `run_continuous()`

```python
while True:
    run_check()  # Query and send alerts
    time.sleep(60)  # Wait 60 seconds
    # Repeat forever
```

- Runs `run_check()` every N seconds (from `MONITOR_INTERVAL`)
- Continues until interrupted (Ctrl+C)
- Logs each iteration

---

## Complete Flow Diagram

```
START
  ↓
Load Config (config.properties, secret.properties)
  ↓
Create APMErrorMonitor
  ↓
Initialize:
  - Connect to Elasticsearch
  - Create query handler
  - Create alert handler
  ↓
[LOOP - Every 60 seconds if continuous mode]
  ↓
Query Elasticsearch:
  - Filter: processor.event = "error"
  - Filter: @timestamp >= now-5m
  - Group by: service.name, service.environment
  - Get: error counts + 3 sample errors
  ↓
Parse Results:
  - errors_by_service_env = [
      {service, environment, error_count, sample_errors},
      ...
    ]
  ↓
For each service/environment with errors:
  ↓
  Get Webhook URL:
    - Check service name in service_webhooks
    - Match: "Media-Meter Global API V2" → MEDIA_METER_WEBHOOK
    - No match → Use SLACK_WEBHOOK (default)
  ↓
  Build Alert:
    - Service name, environment, error count
    - Timestamp (Philippine Time)
    - Sample errors (type, location, message)
  ↓
  Send to Slack:
    - POST to webhook URL
    - Webhook posts to configured channel
  ↓
Log Results
  ↓
Sleep 60 seconds (if continuous)
  ↓
[REPEAT]
```

---

## Key Features

1. **Service-Based Routing**: Each service automatically routes to its dedicated Slack channel
2. **Error Details**: Shows actual error messages, types, and locations
3. **Time Window**: Only alerts on errors in the last 5 minutes (configurable)
4. **Continuous Monitoring**: Runs every 60 seconds (configurable)
5. **Philippine Time**: All timestamps in PHT (UTC+8)
6. **Resilient**: Continues running even if one alert fails

---

## Example Execution

```
1. Monitor starts
2. Queries: "Show me all errors in last 5 minutes"
3. Elasticsearch returns:
   - Media-Meter Global API V2 (production): 7 errors
4. Monitor processes:
   - Service: "Media-Meter Global API V2"
   - Looks up: MEDIA_METER_WEBHOOK
   - Finds: https://hooks.slack.com/.../MEDIA_METER_WEBHOOK
5. Builds alert with:
   - Service name
   - Error count: 7
   - Sample errors (3 most recent)
6. Sends to Slack webhook
7. Slack receives → Posts to #global-api-alerts channel
8. Waits 60 seconds
9. Repeats from step 2
```

