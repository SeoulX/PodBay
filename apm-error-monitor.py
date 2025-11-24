#!/usr/bin/env python3
"""
APM Error Monitor
Entry point script that uses the apm_monitor package.
Queries Elasticsearch for APM errors and sends alerts to webhook.
"""

import sys
import logging
from apm_monitor.monitor import APMErrorMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main execution function."""
    logger.info("Starting APM error monitoring check")
    
    # Initialize monitor
    monitor = APMErrorMonitor()
    
    if not monitor.initialize():
        sys.exit(1)
    
    # Run in continuous mode if MONITOR_INTERVAL is set
    if monitor.config.monitor_interval:
        try:
            interval = int(monitor.config.monitor_interval)
            monitor.run_continuous(interval)
        except ValueError:
            logger.error(f"Invalid MONITOR_INTERVAL value: {monitor.config.monitor_interval}")
            sys.exit(1)
    else:
        # Run once (for CronJob mode)
        if not monitor.run_once():
            sys.exit(1)


if __name__ == "__main__":
    main()

