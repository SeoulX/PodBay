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
        # Service-specific webhooks - load from individual environment variables
        self.service_webhooks = {}
        
        # Map service names to their webhook environment variable names
        service_webhook_mapping = {
            # Salina services -> SALINA_WEBHOOK
            "Salina": "SALINA_WEBHOOK",
            "Salina API v1": "SALINA_WEBHOOK",
            "Salina Auth API": "SALINA_WEBHOOK",
            "Salina Auth API Staging": "SALINA_WEBHOOK",
            # Media-Meter services -> MEDIA_METER_WEBHOOK
            "Media-Meter Global API V2": "MEDIA_METER_WEBHOOK",
            # Scoup services -> SCOUP_WEBHOOK
            "Scoup API Production": "SCOUP_WEBHOOK",
            "Scoup API Staging": "SCOUP_WEBHOOK",
            # Other services
            "Bebot Fast API": "BEBOT_WEBHOOK",
            "Searchsift": "SEARCHSIFT_WEBHOOK",
        }
        
        # Build service_webhooks dict from individual webhook variables
        for service_name, env_var_name in service_webhook_mapping.items():
            webhook_url = os.getenv(env_var_name)
            if webhook_url:
                self.service_webhooks[service_name] = webhook_url
        
        # Jira configuration (optional)
        self.jira_url = os.getenv("JIRA_URL")  # e.g., https://yourcompany.atlassian.net
        self.jira_email = os.getenv("JIRA_EMAIL")  # Email for Jira authentication
        self.jira_api_token = os.getenv("JIRA_API_TOKEN")  # API token from https://id.atlassian.com/manage-profile/security/api-tokens
        self.jira_project_key = os.getenv("JIRA_PROJECT_KEY")  # Project key (e.g., "APM")
        self.jira_issue_type = os.getenv("JIRA_ISSUE_TYPE", "Bug")  # Issue type (default: Bug)
        self.jira_assignee = os.getenv("JIRA_ASSIGNEE")  # Optional assignee username or email
        self.jira_enabled = os.getenv("JIRA_ENABLED", "false").lower() == "true"  # Enable/disable Jira integration
        self.jira_check_duplicates = os.getenv("JIRA_CHECK_DUPLICATES", "true").lower() == "true"  # Check for duplicate tickets
        self.jira_duplicate_lookback_hours = int(os.getenv("JIRA_DUPLICATE_LOOKBACK_HOURS", "24"))  # Hours to look back for duplicates
        
        # Jira labels (comma-separated)
        jira_labels_str = os.getenv("JIRA_LABELS", "")
        self.jira_labels = [label.strip() for label in jira_labels_str.split(",") if label.strip()] if jira_labels_str else []
        
        # Jira components (comma-separated)
        jira_components_str = os.getenv("JIRA_COMPONENTS", "")
        self.jira_components = [comp.strip() for comp in jira_components_str.split(",") if comp.strip()] if jira_components_str else []
        
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
        
        # Validate Jira configuration if enabled
        if self.jira_enabled:
            if not self.jira_url:
                logger.error("JIRA_URL environment variable is required when JIRA_ENABLED=true")
                return False
            if not self.jira_email:
                logger.error("JIRA_EMAIL environment variable is required when JIRA_ENABLED=true")
                return False
            if not self.jira_api_token:
                logger.error("JIRA_API_TOKEN environment variable is required when JIRA_ENABLED=true")
                return False
            if not self.jira_project_key:
                logger.error("JIRA_PROJECT_KEY environment variable is required when JIRA_ENABLED=true")
                return False
        
        return True
    
    def get_jira_config(self):
        """Get Jira client configuration dictionary."""
        if not self.jira_enabled:
            return None
        
        return {
            "jira_url": self.jira_url,
            "email": self.jira_email,
            "api_token": self.jira_api_token,
            "project_key": self.jira_project_key,
            "issue_type": self.jira_issue_type,
            "assignee": self.jira_assignee,
            "labels": self.jira_labels,
            "components": self.jira_components
        }
    
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

