"""
Monitoring module.
Main monitoring logic that orchestrates queries and alerts.
"""

import logging
import sys
import time
from apm_monitor.config import Config
from apm_monitor.elasticsearch_client import ElasticsearchClient
from apm_monitor.queries import APMErrorQueries
from apm_monitor.alerts import WebhookAlerts

logger = logging.getLogger(__name__)


class APMErrorMonitor:
    """Main monitoring class."""
    
    def __init__(self, config=None):
        """
        Initialize the monitor.
        
        Args:
            config: Optional Config object (creates new one if not provided)
        """
        self.config = config or Config()
        self.es_client = None
        self.queries = None
        self.alerts = None
        self.jira_client = None
    
    def initialize(self):
        """
        Initialize Elasticsearch client and other components.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        # Validate configuration
        if not self.config.validate_monitor_config():
            return False
        
        # Initialize Elasticsearch client
        self.es_client = ElasticsearchClient(self.config)
        
        # Check connection
        if not self.es_client.check_connection():
            logger.error("Cannot proceed without Elasticsearch connection")
            return False
        
        # Initialize queries and alerts
        self.queries = APMErrorQueries(self.es_client.get_client())
        jira_url = self.config.jira_url if self.config.jira_enabled else None
        self.alerts = WebhookAlerts(self.config.slack_webhook, self.config.service_webhooks, jira_url=jira_url)
        
        # Initialize Jira client if enabled
        if self.config.jira_enabled:
            try:
                from apm_monitor.jira_client import JiraClient
                jira_config = self.config.get_jira_config()
                if jira_config:
                    self.jira_client = JiraClient(**jira_config)
                    if not self.jira_client.is_connected():
                        logger.warning("Jira integration enabled but connection failed. Continuing without Jira.")
                        self.jira_client = None
                    else:
                        logger.info("Jira integration enabled and connected successfully")
            except ImportError:
                logger.error("Jira integration enabled but 'jira' package is not installed. Install it with: pip install jira")
                self.jira_client = None
        
        return True
    
    def run_check(self):
        """
        Run a single monitoring check.
        
        Returns:
            bool: True if check completed successfully, False otherwise
        """
        # Query for errors grouped by service and environment
        errors_by_service_env, total_errors = self.queries.query_errors_by_service_env(
            self.config.service_name,
            self.config.environment,
            self.config.lookback_minutes
        )
        
        if errors_by_service_env is None:
            logger.error("Failed to query errors from Elasticsearch")
            return False
        
        # Send alerts if errors found
        if total_errors > 0:
            logger.warning(
                f"Alert: {total_errors} total errors detected across "
                f"{len(errors_by_service_env)} service/environment combinations"
            )
            
            # Send individual alerts for each service/environment combination
            alerts_sent = 0
            jira_tickets_created = 0
            for error_info in errors_by_service_env:
                if error_info["error_count"] > 0:
                    sample_errors = error_info.get("sample_errors", [])
                    service_name = error_info["service"]
                    environment = error_info["environment"]
                    
                    # Create Jira ticket first if enabled (so we can include link in Slack)
                    jira_issue = None
                    if self.jira_client and self.jira_client.is_connected():
                        jira_issue = self.jira_client.create_issue(
                            service_name=service_name,
                            environment=environment,
                            error_count=error_info["error_count"],
                            sample_errors=sample_errors,
                            check_duplicates=self.config.jira_check_duplicates,
                            duplicate_lookback_hours=self.config.jira_duplicate_lookback_hours
                        )
                        if jira_issue:
                            jira_tickets_created += 1
                            # Extract unique_id from the issue for logging
                            issue_summary = jira_issue.fields.summary if hasattr(jira_issue.fields, 'summary') else ""
                            issue_description = jira_issue.fields.description if hasattr(jira_issue.fields, 'description') else ""
                            unique_id = self.jira_client._extract_unique_id(issue_description, issue_summary) if self.jira_client else None
                            if unique_id:
                                logger.info(
                                    f"Created Jira ticket {unique_id} (Jira: {jira_issue.key}) for {service_name}/{environment}"
                                )
                            else:
                                logger.info(
                                    f"Created Jira ticket {jira_issue.key} for {service_name}/{environment}"
                                )
                    
                    # Extract unique_id from the issue for Slack alert
                    jira_issue_key = None
                    jira_unique_id = None
                    if jira_issue:
                        jira_issue_key = jira_issue.key
                        # Extract unique_id from the issue
                        issue_summary = jira_issue.fields.summary if hasattr(jira_issue.fields, 'summary') else ""
                        issue_description = jira_issue.fields.description if hasattr(jira_issue.fields, 'description') else ""
                        if self.jira_client:
                            jira_unique_id = self.jira_client._extract_unique_id(issue_description, issue_summary)
                    
                    # Send Slack alert (include Jira ticket link if available)
                    if self.alerts.send_alert(
                        service_name,
                        error_info["error_count"],
                        environment,
                        sample_errors=sample_errors,
                        jira_issue_key=jira_issue_key,
                        jira_unique_id=jira_unique_id
                    ):
                        alerts_sent += 1
                    else:
                        logger.warning(
                            f"Failed to send alert for {service_name}/{environment}"
                        )
            
            logger.info(f"Sent {alerts_sent} individual alerts")
            if self.jira_client:
                logger.info(f"Created/updated {jira_tickets_created} Jira tickets")
        else:
            logger.info("No errors detected across all services and environments")
        
        return True
    
    def run_continuous(self, interval):
        """
        Run monitoring in continuous mode.
        
        Args:
            interval: Interval in seconds between checks
        """
        logger.info(f"Running in continuous mode with {interval} second interval")
        try:
            while True:
                if not self.run_check():
                    logger.warning("Check failed, will retry on next interval")
                logger.info(f"Sleeping for {interval} seconds...")
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down")
            sys.exit(0)
    
    def run_once(self):
        """
        Run monitoring once (for CronJob mode).
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.run_check():
            return False
        logger.info("APM error monitoring check completed successfully")
        return True

