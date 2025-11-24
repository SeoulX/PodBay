#!/usr/bin/env python3
"""
APM Error Monitor
Queries Elasticsearch for APM errors and sends alerts to webhook.
"""

import os
import sys
import time
import logging
from datetime import datetime, timezone
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, RequestError
import requests
from requests.exceptions import RequestException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://elasticsearch:9200")
ELASTICSEARCH_USERNAME = os.getenv("ELASTICSEARCH_USERNAME")
ELASTICSEARCH_PASSWORD = os.getenv("ELASTICSEARCH_PASSWORD")
SERVICE_NAME = os.getenv("SERVICE_NAME")  # Optional: filter by specific service, or None for all services
ENVIRONMENT = os.getenv("ENVIRONMENT")  # Optional: filter by specific environment, or None for all environments
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK")
LOOKBACK_MINUTES = int(os.getenv("LOOKBACK_MINUTES", "5"))
MONITOR_INTERVAL = os.getenv("MONITOR_INTERVAL")  # If set, run in continuous mode

# Validate required configuration
if not SLACK_WEBHOOK:
    logger.error("SLACK_WEBHOOK environment variable is not set")
    sys.exit(1)


def check_elasticsearch_connection(es):
    """Check if Elasticsearch is accessible."""
    try:
        # Try to get cluster info instead of ping (more reliable)
        info = es.info()
        if info:
            logger.info(f"Successfully connected to Elasticsearch cluster: {info.get('cluster_name', 'unknown')}")
            return True
        else:
            logger.error("Failed to get Elasticsearch info")
            return False
    except (ConnectionError, RequestError) as e:
        logger.error(f"Failed to connect to Elasticsearch: {e}")
        # Try ping as fallback
        try:
            if es.ping():
                logger.info("Successfully connected to Elasticsearch (via ping)")
                return True
        except:
            pass
        return False
    except Exception as e:
        logger.error(f"Unexpected error connecting to Elasticsearch: {e}")
        return False


def query_apm_errors_by_service_env(es, service_name, environment, lookback_minutes):
    """Query Elasticsearch for APM errors grouped by service and environment."""
    try:
        # Build query filters
        filters = [
            {"term": {"processor.event": "error"}},
            {"range": {"@timestamp": {"gte": f"now-{lookback_minutes}m"}}}
        ]
        
        # Add service filter if specified
        if service_name:
            # Try keyword field first, fallback to text field
            filters.append({"term": {"service.name.keyword": service_name}})
            logger.info(f"Filtering by service: {service_name}")
        else:
            logger.info("Querying all services")
        
        # Add environment filter if specified
        if environment:
            # Try keyword field first, fallback to text field
            filters.append({"term": {"service.environment.keyword": environment}})
            logger.info(f"Filtering by environment: {environment}")
        else:
            logger.info("Querying all environments")
        
        query_body = {
            "query": {
                "bool": {
                    "filter": filters
                }
            },
            "size": 0,  # We don't need the actual documents
            "aggs": {
                "by_service": {
                    "terms": {
                        "field": "service.name.keyword",  # Use keyword field for aggregations
                        "size": 1000,  # Support up to 1000 services
                        "missing": "unknown"  # Handle missing values
                    },
                    "aggs": {
                        "by_environment": {
                            "terms": {
                                "field": "service.environment.keyword",  # Use keyword field for aggregations
                                "size": 100,  # Support up to 100 environments per service
                                "missing": "unknown"  # Handle missing values
                            }
                        }
                    }
                }
            }
        }
        
        logger.info(f"Querying APM errors in last {lookback_minutes} minutes")
        res = es.search(
            index="apm-*",
            body=query_body
        )
        
        # Parse aggregation results
        errors_by_service_env = []
        total_errors = 0
        
        if "aggregations" in res and "by_service" in res["aggregations"]:
            for service_bucket in res["aggregations"]["by_service"]["buckets"]:
                service = service_bucket["key"]
                service_total = service_bucket["doc_count"]
                
                # Get environment breakdown
                if "by_environment" in service_bucket:
                    for env_bucket in service_bucket["by_environment"]["buckets"]:
                        env = env_bucket["key"]
                        env_count = env_bucket["doc_count"]
                        errors_by_service_env.append({
                            "service": service,
                            "environment": env,
                            "error_count": env_count
                        })
                        total_errors += env_count
                else:
                    # No environment field, use "unknown"
                    errors_by_service_env.append({
                        "service": service,
                        "environment": "unknown",
                        "error_count": service_total
                    })
                    total_errors += service_total
        
        logger.info(f"Found {total_errors} total errors across {len(errors_by_service_env)} service/environment combinations")
        
        return errors_by_service_env, total_errors
    except RequestError as e:
        logger.error(f"Elasticsearch query error: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Unexpected error querying Elasticsearch: {e}")
        return None, None


def send_webhook_alert(webhook_url, service_name, error_count, environment):
    """Send alert to webhook (Slack) for a specific service/environment."""
    # Format message for Slack
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    text = f"🚨 *APM Error Alert*\n\n*Service:* {service_name}\n*Environment:* {environment}\n*Error Count:* {error_count}\n*Time:* {timestamp}"
    
    # Slack webhook format
    payload = {
        "text": text,
        "attachments": [
            {
                "color": "danger",
                "fields": [
                    {
                        "title": "Service",
                        "value": service_name,
                        "short": True
                    },
                    {
                        "title": "Environment",
                        "value": environment,
                        "short": True
                    },
                    {
                        "title": "Error Count",
                        "value": str(error_count),
                        "short": True
                    },
                    {
                        "title": "Time",
                        "value": timestamp,
                        "short": True
                    }
                ]
            }
        ]
    }
    
    try:
        logger.info(f"Sending alert to webhook for {service_name}/{environment}: {error_count} errors")
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Successfully sent alert to webhook. Status: {response.status_code}")
        return True
    except RequestException as e:
        logger.error(f"Failed to send webhook alert: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response: {e.response.text}")
        return False


def send_summary_webhook_alert(webhook_url, errors_by_service_env, total_errors):
    """Send summary alert with all service/environment combinations."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Build summary text
    summary_lines = [f"📊 *APM Error Summary*\n\n*Total Errors:* {total_errors}\n*Affected Services:* {len(errors_by_service_env)}\n*Time:* {timestamp}\n"]
    
    # Add details for each service/environment
    details = []
    for error_info in errors_by_service_env:
        details.append(f"• {error_info['service']} ({error_info['environment']}): {error_info['error_count']} errors")
    
    summary_lines.append("\n*Details:*\n" + "\n".join(details))
    
    # Slack webhook format
    payload = {
        "text": "".join(summary_lines),
        "attachments": [
            {
                "color": "warning",
                "fields": [
                    {
                        "title": "Total Errors",
                        "value": str(total_errors),
                        "short": True
                    },
                    {
                        "title": "Affected Services",
                        "value": str(len(errors_by_service_env)),
                        "short": True
                    },
                    {
                        "title": "Time",
                        "value": timestamp,
                        "short": False
                    }
                ]
            }
        ]
    }
    
    try:
        logger.info(f"Sending summary alert to webhook: {total_errors} total errors across {len(errors_by_service_env)} combinations")
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Successfully sent summary alert to webhook. Status: {response.status_code}")
        return True
    except RequestException as e:
        logger.error(f"Failed to send summary webhook alert: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response: {e.response.text}")
        return False


def run_check(es):
    """Run a single monitoring check."""
    # Query for errors grouped by service and environment
    errors_by_service_env, total_errors = query_apm_errors_by_service_env(
        es, SERVICE_NAME, ENVIRONMENT, LOOKBACK_MINUTES
    )
    
    if errors_by_service_env is None:
        logger.error("Failed to query errors from Elasticsearch")
        return False
    
    # Send alerts if errors found
    if total_errors > 0:
        logger.warning(f"Alert: {total_errors} total errors detected across {len(errors_by_service_env)} service/environment combinations")
        
        # Send individual alerts for each service/environment combination
        alerts_sent = 0
        for error_info in errors_by_service_env:
            if error_info["error_count"] > 0:
                if send_webhook_alert(
                    SLACK_WEBHOOK,
                    error_info["service"],
                    error_info["error_count"],
                    error_info["environment"]
                ):
                    alerts_sent += 1
                else:
                    logger.warning(f"Failed to send alert for {error_info['service']}/{error_info['environment']}")
        
        # Also send a summary alert
        if not send_summary_webhook_alert(SLACK_WEBHOOK, errors_by_service_env, total_errors):
            logger.warning("Failed to send summary alert, but individual alerts were sent")
        
        logger.info(f"Sent {alerts_sent} individual alerts and 1 summary alert")
    else:
        logger.info("No errors detected across all services and environments")
    
    return True


def main():
    """Main execution function."""
    logger.info("Starting APM error monitoring check")
    
    # Initialize Elasticsearch client with authentication if provided
    es_config = {
        "hosts": [ELASTICSEARCH_HOST],
        "verify_certs": False,  # Set to True in production with proper certificates
        "ssl_show_warn": False,
        "request_timeout": 30
    }
    
    # Add basic authentication if credentials are provided
    if ELASTICSEARCH_USERNAME and ELASTICSEARCH_PASSWORD:
        logger.info("Using basic authentication for Elasticsearch")
        es_config["basic_auth"] = (ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD)
    else:
        logger.info("Connecting to Elasticsearch without authentication")
    
    es = Elasticsearch(**es_config)
    
    # Check connection
    if not check_elasticsearch_connection(es):
        logger.error("Cannot proceed without Elasticsearch connection")
        sys.exit(1)
    
    # Run in continuous mode if MONITOR_INTERVAL is set
    if MONITOR_INTERVAL:
        try:
            interval = int(MONITOR_INTERVAL)
            logger.info(f"Running in continuous mode with {interval} second interval")
            while True:
                if not run_check(es):
                    logger.warning("Check failed, will retry on next interval")
                logger.info(f"Sleeping for {interval} seconds...")
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down")
            sys.exit(0)
        except ValueError:
            logger.error(f"Invalid MONITOR_INTERVAL value: {MONITOR_INTERVAL}")
            sys.exit(1)
    else:
        # Run once (for CronJob mode)
        if not run_check(es):
            sys.exit(1)
        logger.info("APM error monitoring check completed successfully")


if __name__ == "__main__":
    main()

