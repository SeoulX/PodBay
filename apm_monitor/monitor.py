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
        self.alerts = WebhookAlerts(self.config.slack_webhook)
        
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
            for error_info in errors_by_service_env:
                if error_info["error_count"] > 0:
                    sample_errors = error_info.get("sample_errors", [])
                    if self.alerts.send_alert(
                        error_info["service"],
                        error_info["error_count"],
                        error_info["environment"],
                        sample_errors=sample_errors
                    ):
                        alerts_sent += 1
                    else:
                        logger.warning(
                            f"Failed to send alert for "
                            f"{error_info['service']}/{error_info['environment']}"
                        )
            
            logger.info(f"Sent {alerts_sent} individual alerts")
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

