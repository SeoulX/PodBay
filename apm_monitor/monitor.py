"""
Monitoring module.
Main monitoring logic that orchestrates queries and alerts.
"""

import logging
import sys
import time
from datetime import datetime, timezone, timedelta
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
        self.last_jira_success_time = None  # Track when JIRA was last successfully connected
    
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
        
        # Initialize Jira client if enabled (but don't fail if connection fails - will retry later)
        if self.config.jira_enabled:
            try:
                from apm_monitor.jira_client import JiraClient
                jira_config = self.config.get_jira_config()
                if jira_config:
                    self.jira_client = JiraClient(**jira_config)
                    if not self.jira_client.is_connected():
                        logger.warning("Jira integration enabled but initial connection failed. Will retry on next monitoring interval.")
                    else:
                        logger.info("Jira integration enabled and connected successfully")
                        self.last_jira_success_time = datetime.now(timezone.utc)
            except ImportError:
                logger.error("Jira integration enabled but 'jira' package is not installed. Install it with: pip install jira")
                self.jira_client = None
        
        return True
    
    def _catch_up_missed_jira_tickets(self):
        """
        Catch up on creating JIRA tickets for errors that occurred while JIRA was down.
        Queries errors from the last successful JIRA connection time (or max 24 hours).
        """
        if not self.jira_client or not self.jira_client.is_connected():
            return
        
        if not self.last_jira_success_time:
            # First time connecting, no catch-up needed
            self.last_jira_success_time = datetime.now(timezone.utc)
            return
        
        now = datetime.now(timezone.utc)
        downtime_duration = (now - self.last_jira_success_time).total_seconds() / 60  # in minutes
        
        # Only catch up if JIRA was down for more than one monitoring interval
        # and less than 24 hours (to avoid processing too much data)
        max_catchup_minutes = 24 * 60  # 24 hours
        monitor_interval_minutes = int(self.config.monitor_interval) / 60 if self.config.monitor_interval else 1
        if downtime_duration < monitor_interval_minutes:
            # JIRA was down for less than one monitoring interval, no catch-up needed
            self.last_jira_success_time = now
            return
        
        catchup_minutes = min(int(downtime_duration), max_catchup_minutes)
        logger.info(
            f"JIRA was down for {downtime_duration:.1f} minutes. "
            f"Catching up on errors from the last {catchup_minutes} minutes..."
        )
        
        # Query errors from the downtime period
        errors_by_service_env, total_errors = self.queries.query_errors_by_service_env(
            self.config.service_name,
            self.config.environment,
            catchup_minutes
        )
        
        if errors_by_service_env is None:
            logger.error("Failed to query errors for catch-up")
            self.last_jira_success_time = now
            return
        
        if total_errors == 0:
            logger.info("No errors found during JIRA downtime period")
            self.last_jira_success_time = now
            return
        
        # Create JIRA tickets for missed errors
        tickets_created = 0
        for error_info in errors_by_service_env:
            if error_info["error_count"] > 0:
                sample_errors = error_info.get("sample_errors", [])
                service_name = error_info["service"]
                environment = error_info["environment"]
                
                jira_issue = self.jira_client.create_issue(
                    service_name=service_name,
                    environment=environment,
                    error_count=error_info["error_count"],
                    sample_errors=sample_errors,
                    check_duplicates=self.config.jira_check_duplicates,
                    duplicate_lookback_hours=self.config.jira_duplicate_lookback_hours
                )
                if jira_issue:
                    tickets_created += 1
                    logger.info(
                        f"Created catch-up JIRA ticket {jira_issue.key} for {service_name}/{environment} "
                        f"({error_info['error_count']} errors during downtime)"
                    )
        
        logger.info(
            f"Catch-up complete: Created {tickets_created} JIRA tickets for {total_errors} errors "
            f"that occurred during {downtime_duration:.1f} minutes of JIRA downtime"
        )
        self.last_jira_success_time = now
    
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
                    jira_was_reconnected = False
                    # Try to initialize or reconnect if JIRA is enabled but not connected
                    if self.config.jira_enabled:
                        if not self.jira_client:
                            # Try to initialize JIRA client if it wasn't created before
                            try:
                                from apm_monitor.jira_client import JiraClient
                                jira_config = self.config.get_jira_config()
                                if jira_config:
                                    logger.info("Attempting to initialize JIRA client...")
                                    self.jira_client = JiraClient(**jira_config)
                                    if self.jira_client.is_connected():
                                        jira_was_reconnected = True
                                        # Catch up on missed errors
                                        self._catch_up_missed_jira_tickets()
                            except ImportError:
                                logger.error("Jira integration enabled but 'jira' package is not installed")
                        elif not self.jira_client.is_connected():
                            # Try to reconnect if client exists but not connected
                            logger.info("JIRA is enabled but not connected, attempting to reconnect...")
                            if self.jira_client.reconnect():
                                jira_was_reconnected = True
                                # Catch up on missed errors
                                self._catch_up_missed_jira_tickets()
                    
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
                            # Update last success time when ticket is created
                            self.last_jira_success_time = datetime.now(timezone.utc)
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
                    elif self.config.jira_enabled:
                        # JIRA is enabled but not connected - errors are still tracked in Elasticsearch
                        logger.warning(
                            f"JIRA is not connected. Skipping ticket creation for {service_name}/{environment} "
                            f"({error_info['error_count']} errors). Errors are still tracked in Elasticsearch and "
                            f"tickets will be created automatically when JIRA reconnects (within {self.config.lookback_minutes} minute lookback window)."
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

