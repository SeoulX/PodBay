"""
Alerting module.
Handles sending alerts to webhooks (Slack).
"""

import logging
from datetime import datetime, timezone
import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class WebhookAlerts:
    """Class for sending webhook alerts."""
    
    def __init__(self, webhook_url):
        """
        Initialize webhook alerts.
        
        Args:
            webhook_url: Slack webhook URL
        """
        self.webhook_url = webhook_url
    
    def send_alert(self, service_name, error_count, environment, sample_errors=None):
        """
        Send alert to webhook (Slack) for a specific service/environment.
        
        Args:
            service_name: Name of the service
            error_count: Number of errors detected
            environment: Environment name
            sample_errors: Optional list of sample error details
        
        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        # Format message for Slack
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        text = (
            f"🚨 *APM Error Alert*\n\n"
            f"*Service:* {service_name}\n"
            f"*Environment:* {environment}\n"
            f"*Error Count:* {error_count}\n"
            f"*Time:* {timestamp}"
        )
        
        # Build fields for attachment
        fields = [
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
        
        # Add error details if available
        if sample_errors and len(sample_errors) > 0:
            error_details = []
            for i, err in enumerate(sample_errors[:3], 1):  # Show up to 3 sample errors
                error_msg = err.get("message", "")
                error_type = err.get("type", "")
                error_culprit = err.get("culprit", "")
                
                detail = f"*Error {i}:*"
                if error_type:
                    detail += f"\nType: {error_type}"
                if error_culprit:
                    detail += f"\nLocation: {error_culprit}"
                if error_msg:
                    # Truncate very long messages for Slack
                    msg = error_msg[:300] + "..." if len(error_msg) > 300 else error_msg
                    detail += f"\nMessage: {msg}"
                
                error_details.append(detail)
            
            if error_details:
                fields.append({
                    "title": "Sample Errors",
                    "value": "\n\n".join(error_details),
                    "short": False
                })
        
        # Slack webhook format
        payload = {
            "text": text,
            "attachments": [
                {
                    "color": "danger",
                    "fields": fields
                }
            ]
        }
        
        try:
            logger.info(
                f"Sending alert to webhook for {service_name}/{environment}: "
                f"{error_count} errors"
            )
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Successfully sent alert to webhook. Status: {response.status_code}")
            return True
        except RequestException as e:
            logger.error(f"Failed to send webhook alert: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return False
    
    def send_summary_alert(self, errors_by_service_env, total_errors):
        """
        Send summary alert with all service/environment combinations.
        
        Args:
            errors_by_service_env: List of dicts with service, environment, and error_count
            total_errors: Total number of errors across all services/environments
        
        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Build summary text
        summary_lines = [
            f"📊 *APM Error Summary*\n\n"
            f"*Total Errors:* {total_errors}\n"
            f"*Affected Services:* {len(errors_by_service_env)}\n"
            f"*Time:* {timestamp}\n"
        ]
        
        # Add details for each service/environment
        details = []
        for error_info in errors_by_service_env:
            details.append(
                f"• {error_info['service']} ({error_info['environment']}): "
                f"{error_info['error_count']} errors"
            )
        
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
            logger.info(
                f"Sending summary alert to webhook: {total_errors} total errors "
                f"across {len(errors_by_service_env)} combinations"
            )
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Successfully sent summary alert to webhook. Status: {response.status_code}")
            return True
        except RequestException as e:
            logger.error(f"Failed to send summary webhook alert: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return False

