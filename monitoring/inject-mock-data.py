#!/usr/bin/env python3
"""
Mock APM Error Data Injector
Injects test APM error data into Elasticsearch for testing the monitoring script.
"""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, RequestError

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

# Mock data configuration
NUM_ERRORS = int(os.getenv("NUM_ERRORS", "5"))  # Number of errors to inject
SERVICES = os.getenv("SERVICES", "fastapi-app,web-service,api-gateway").split(",")
ENVIRONMENTS = os.getenv("ENVIRONMENTS", "production,staging,development").split(",")


def create_elasticsearch_client():
    """Create and return Elasticsearch client."""
    es_config = {
        "hosts": [ELASTICSEARCH_HOST],
        "verify_certs": False,
        "ssl_show_warn": False,
        "request_timeout": 30
    }
    
    if ELASTICSEARCH_USERNAME and ELASTICSEARCH_PASSWORD:
        es_config["basic_auth"] = (ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD)
    
    return Elasticsearch(**es_config)


def check_connection(es):
    """Check Elasticsearch connection."""
    try:
        info = es.info()
        logger.info(f"Connected to Elasticsearch cluster: {info.get('cluster_name', 'unknown')}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to Elasticsearch: {e}")
        return False


def generate_mock_error_document(service_name, environment, timestamp):
    """Generate a mock APM error document."""
    return {
        "@timestamp": timestamp.isoformat(),
        "processor": {
            "event": "error"
        },
        "service": {
            "name": service_name,
            "environment": environment,
            "version": "1.0.0"
        },
        "error": {
            "id": f"error-{timestamp.timestamp()}",
            "type": "Exception",
            "message": f"Mock error in {service_name} ({environment})",
            "exception": {
                "type": "ValueError",
                "message": "This is a test error for monitoring validation",
                "stacktrace": [
                    {
                        "filename": "app.py",
                        "line": {
                            "number": 42
                        },
                        "function": "process_request"
                    }
                ]
            }
        },
        "transaction": {
            "id": f"tx-{timestamp.timestamp()}",
            "type": "request"
        },
        "labels": {
            "test": "true",
            "mock_data": "true"
        }
    }


def inject_mock_data(es, num_errors, services, environments):
    """Inject mock APM error data into Elasticsearch."""
    logger.info(f"Injecting {num_errors} mock errors across {len(services)} services and {len(environments)} environments")
    
    # Calculate time range - errors in the last 5 minutes
    now = datetime.now(timezone.utc)
    time_range_minutes = 5
    
    errors_injected = 0
    errors_failed = 0
    
    for i in range(num_errors):
        # Randomly select service and environment
        import random
        service = random.choice(services)
        environment = random.choice(environments)
        
        # Generate timestamp within the last 5 minutes
        minutes_ago = random.uniform(0, time_range_minutes)
        timestamp = now - timedelta(minutes=minutes_ago)
        
        # Generate mock error document
        doc = generate_mock_error_document(service, environment, timestamp)
        
        try:
            # Index the document
            # APM indices follow the pattern: apm-*-error-YYYY.MM.DD
            index_date = timestamp.strftime("%Y.%m.%d")
            index_name = f"apm-8.0.0-error-{index_date}"
            
            response = es.index(
                index=index_name,
                document=doc,
                refresh=True  # Make it immediately searchable
            )
            
            if response.get("result") in ["created", "updated"]:
                errors_injected += 1
                logger.debug(f"Injected error {i+1}/{num_errors}: {service}/{environment} at {timestamp.isoformat()}")
            else:
                errors_failed += 1
                logger.warning(f"Failed to inject error {i+1}/{num_errors}")
                
        except Exception as e:
            errors_failed += 1
            logger.error(f"Error injecting document {i+1}: {e}")
    
    logger.info(f"Injection complete: {errors_injected} succeeded, {errors_failed} failed")
    return errors_injected, errors_failed


def main():
    """Main execution function."""
    logger.info("Starting mock APM error data injection")
    
    # Create Elasticsearch client
    es = create_elasticsearch_client()
    
    # Check connection
    if not check_connection(es):
        logger.error("Cannot proceed without Elasticsearch connection")
        sys.exit(1)
    
    # Inject mock data
    errors_injected, errors_failed = inject_mock_data(es, NUM_ERRORS, SERVICES, ENVIRONMENTS)
    
    if errors_injected > 0:
        logger.info(f"Successfully injected {errors_injected} mock errors")
        logger.info("You can now run the monitoring script to test alerting:")
        logger.info("  python3 apm-error-monitor.py")
        
        if errors_failed > 0:
            logger.warning(f"Failed to inject {errors_failed} errors")
            sys.exit(1)
    else:
        logger.error("Failed to inject any errors")
        sys.exit(1)


if __name__ == "__main__":
    main()

