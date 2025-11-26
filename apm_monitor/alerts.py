"""
Alerting module.
Handles sending alerts to webhooks (Slack).
"""

import logging
from datetime import datetime, timezone, timedelta
import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


def truncate_pod_name(pod_name):
    """
    Truncate pod name by removing -production-* suffix.
    
    Example:
        "global-fast-api-deploy-production-6bf7854c57-wfft9" 
        -> "global-fast-api-deploy"
    
    Args:
        pod_name: Full pod name
    
    Returns:
        str: Truncated pod name, or original if no -production- found
    """
    if not pod_name:
        return ""
    
    # Find the position of "-production-"
    idx = pod_name.find("-production-")
    if idx != -1:
        return pod_name[:idx]
    
    return pod_name


class WebhookAlerts:
    """Class for sending webhook alerts."""
    
    def __init__(self, webhook_url, service_webhooks=None, jira_url=None):
        """
        Initialize webhook alerts.
        
        Args:
            webhook_url: Default Slack webhook URL
            service_webhooks: Optional dict mapping service names to webhook URLs
            jira_url: Optional Jira server URL for creating ticket links
        """
        self.default_webhook_url = webhook_url
        self.service_webhooks = service_webhooks or {}
        self.jira_url = jira_url
        # Service name to channel mapping (for channel override in payload)
        # Note: Channel override in webhook payload may not work in all Slack setups.
        # The most reliable method is to use separate webhook URLs per channel via SERVICE_WEBHOOKS.
        # This mapping is kept for cases where channel override is supported.
        self.service_channel_map = {
            # Salina services -> #salina-alerts
            "Salina": "#salina-alerts",
            "Salina API v1": "#salina-alerts",
            "Salina Auth API": "#salina-alerts",
            "Salina Auth API Staging": "#salina-alerts",
            # Media-Meter services -> #media-meter-alerts
            "Media-Meter Global API V2": "#global-api-alerts",
            # Scoup services -> #scoup-alerts (or default channel)
            "Scoup API Production": "#scoup-alerts",
            "Scoup API Staging": "#scoup-alerts",
            # Other services
            "Bebot Fast API": "#bebot-alerts",
            "Searchsift": "#searchsift-alerts",
        }
    
    def get_webhook_url_for_service(self, service_name):
        """
        Get the webhook URL for a given service name.
        
        Args:
            service_name: Name of the service
        
        Returns:
            str: Webhook URL for the service, or default webhook URL
        """
        # Check exact match first
        if service_name in self.service_webhooks:
            logger.debug(f"Exact match found for service '{service_name}'")
            return self.service_webhooks[service_name]
        
        # Check partial match (e.g., "Salina" in "Salina API v1")
        for key, webhook_url in self.service_webhooks.items():
            if key.lower() in service_name.lower() or service_name.lower() in key.lower():
                logger.debug(f"Partial match found: '{key}' matches '{service_name}'")
                return webhook_url
        
        # Default webhook
        logger.debug(f"No match found for service '{service_name}', using default webhook")
        return self.default_webhook_url
    
    def get_channel_for_service(self, service_name):
        """
        Get the Slack channel for a given service name.
        
        Args:
            service_name: Name of the service
        
        Returns:
            str: Channel name (e.g., "#salina-alerts") or None for default channel
        """
        # Check exact match first
        if service_name in self.service_channel_map:
            return self.service_channel_map[service_name]
        
        # Check partial match (e.g., "Salina" in "Salina API v1")
        for key, channel in self.service_channel_map.items():
            if key.lower() in service_name.lower() or service_name.lower() in key.lower():
                return channel
        
        # Default channel (None means use webhook's default channel)
        return None
    
    def send_alert(self, service_name, error_count, environment, sample_errors=None, jira_issue_key=None, jira_unique_id=None):
        """
        Send alert to webhook (Slack) for a specific service/environment.
        
        Args:
            service_name: Name of the service
            error_count: Number of errors detected
            environment: Environment name
            sample_errors: Optional list of sample error details
            jira_issue_key: Optional Jira issue key (e.g., DDT-1) to include in the alert
            jira_unique_id: Optional unique ID (e.g., DO-112625-20251126) to display instead of Jira key
        
        Returns:
            bool: True if alert was sent successfully, False otherwise
        """
        # Format message for Slack (Philippine Time, UTC+8)
        ph_timezone = timezone(timedelta(hours=8))
        timestamp = datetime.now(ph_timezone).strftime("%Y-%m-%d %H:%M:%S PHT")
        text = (
            f"🚨 *APM Error Alert*\n\n"
            f"*Service:* {service_name}\n"
        )
        
        # Build fields for attachment
        fields = [
            {
                "title": "Service",
                "value": f"`{service_name}`",
                "short": True
            },
            {
                "title": "Environment",
                "value": f"`{environment}`",
                "short": True
            },
            {
                "title": "Error Count",
                "value": f"`{error_count}`",
                "short": True
            },
            {
                "title": "Time",
                "value": f"`{timestamp}`",
                "short": True
            }
        ]
        
        # Add Jira ticket link if available
        if jira_issue_key:
            # Use unique_id if available, otherwise use Jira key
            display_id = jira_unique_id if jira_unique_id else jira_issue_key
            if self.jira_url:
                # Construct full Jira URL (always use Jira key for the link)
                jira_link = f"{self.jira_url}/browse/{jira_issue_key}"
                fields.append({
                    "title": "Jira Ticket",
                    "value": f"<{jira_link}|{display_id}>",
                    "short": True
                })
            else:
                # Just show the display ID if URL not available
                fields.append({
                    "title": "Jira Ticket",
                    "value": f"`{display_id}`",
                    "short": True
                })
        
        # Add error details if available
        if sample_errors and len(sample_errors) > 0:
            error_details = []
            for i, err in enumerate(sample_errors[:1], 1):  # Show up to 1 sample error
                error_msg = err.get("message", "")
                error_type = err.get("type", "")
                error_culprit = err.get("culprit", "")
                pod_name = err.get("pod_name", "")
                
                detail = f"*Error {i}:*\n\n"
                
                if pod_name:
                    truncated_pod = truncate_pod_name(pod_name)
                    detail += f"Pod: `{truncated_pod}`\n"
                
                if error_type:
                    detail += f"Type: `{error_type}`\n"
                
                if error_culprit:
                    detail += f"Location: `{error_culprit}`\n"
                
                detail += "Message:\n"
                if error_msg:
                    # Truncate very long messages for Slack
                    msg = error_msg[:300] + "..." if len(error_msg) > 300 else error_msg
                    # Format error message as code block
                    detail += f"```\n{msg}\n```"
                
                error_details.append(detail)
            
            if error_details:
                fields.append({
                    "title": "Sample Errors",
                    "value": "\n\n".join(error_details),
                    "short": False
                })
        
        # Get webhook URL for this service
        # Note: Each webhook URL is configured for its specific channel in Slack
        webhook_url = self.get_webhook_url_for_service(service_name)
        
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
            # Log which webhook is being used
            if service_name in self.service_webhooks:
                logger.info(
                    f"Sending alert using service-specific webhook for {service_name}/{environment}: "
                    f"{error_count} errors"
                )
                logger.debug(f"Webhook URL: {webhook_url[:60]}...")
            else:
                # Check if partial match was used
                matched = False
                for key in self.service_webhooks.keys():
                    if key.lower() in service_name.lower() or service_name.lower() in key.lower():
                        logger.info(
                            f"Sending alert using service-specific webhook (matched '{key}') for {service_name}/{environment}: "
                            f"{error_count} errors"
                        )
                        logger.debug(f"Webhook URL: {webhook_url[:60]}...")
                        matched = True
                        break
                if not matched:
                    logger.info(
                        f"Sending alert using default webhook for {service_name}/{environment}: "
                        f"{error_count} errors"
                    )
                    logger.debug(f"Webhook URL: {webhook_url[:60]}...")
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Successfully sent alert to webhook. Status: {response.status_code}")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error sending webhook alert for {service_name}/{environment}: {e}")
            if e.response is not None:
                logger.error(f"HTTP Status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error sending webhook alert for {service_name}/{environment}: {e}")
            logger.error(f"Webhook URL used: {webhook_url[:80]}...")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending webhook alert for {service_name}/{environment}: {e}")
            logger.exception(e)
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
        # Philippine Time (UTC+8)
        ph_timezone = timezone(timedelta(hours=8))
        timestamp = datetime.now(ph_timezone).strftime("%Y-%m-%d %H:%M:%S PHT")
        
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

