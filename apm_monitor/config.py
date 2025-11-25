"""
Configuration management module.
Handles loading and validation of configuration from environment variables.
"""

import os
import sys
import logging

logger = logging.getLogger(__name__)


class Config:
    """Configuration class for APM Error Monitor."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Elasticsearch configuration
        self.elasticsearch_host = os.getenv(
            "ELASTICSEARCH_HOST", 
            "http://elasticsearch:9200"
        )
        self.elasticsearch_username = os.getenv("ELASTICSEARCH_USERNAME")
        self.elasticsearch_password = os.getenv("ELASTICSEARCH_PASSWORD")
        
        # Service and environment filters
        self.service_name = os.getenv("SERVICE_NAME")  # Optional: filter by specific service
        self.environment = os.getenv("ENVIRONMENT")  # Optional: filter by specific environment
        
        # Monitoring configuration
        self.lookback_minutes = int(os.getenv("LOOKBACK_MINUTES", "5"))
        self.monitor_interval = os.getenv("MONITOR_INTERVAL")  # Optional: for continuous mode
        
        # Webhook configuration
        self.slack_webhook = os.getenv("SLACK_WEBHOOK")
        # Service-specific webhooks (format: "ServiceName:webhook_url,ServiceName2:webhook_url2")
        # Example: "Salina:https://hooks.slack.com/...,Media-Meter:https://hooks.slack.com/..."
        self.service_webhooks = {}
        service_webhooks_str = os.getenv("SERVICE_WEBHOOKS", "")
        if service_webhooks_str:
            for mapping in service_webhooks_str.split(","):
                if ":" in mapping:
                    service, webhook = mapping.split(":", 1)
                    self.service_webhooks[service.strip()] = webhook.strip()
        
        # Mock data configuration
        self.num_errors = int(os.getenv("NUM_ERRORS", "5"))
        self.services = os.getenv(
            "SERVICES", 
            "fastapi-app,web-service,api-gateway"
        ).split(",")
        self.environments = os.getenv(
            "ENVIRONMENTS", 
            "production,staging,development"
        ).split(",")
    
    def validate_monitor_config(self):
        """Validate configuration required for monitoring."""
        if not self.slack_webhook:
            logger.error("SLACK_WEBHOOK environment variable is not set")
            return False
        return True
    
    def get_elasticsearch_config(self):
        """Get Elasticsearch client configuration dictionary."""
        es_config = {
            "hosts": [self.elasticsearch_host],
            "verify_certs": False,  # Set to True in production with proper certificates
            "ssl_show_warn": False,
            "request_timeout": 30
        }
        
        # Add basic authentication if credentials are provided
        if self.elasticsearch_username and self.elasticsearch_password:
            logger.info("Using basic authentication for Elasticsearch")
            es_config["basic_auth"] = (
                self.elasticsearch_username, 
                self.elasticsearch_password
            )
        else:
            logger.info("Connecting to Elasticsearch without authentication")
        
        return es_config

