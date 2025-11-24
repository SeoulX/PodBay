#!/usr/bin/env python3
"""
Mock APM Error Data Injector
Entry point script that uses the apm_monitor package.
Injects test APM error data into Elasticsearch for testing the monitoring script.
"""

import sys
import logging
from apm_monitor.mock_data import MockDataInjector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main execution function."""
    logger.info("Starting mock APM error data injection")
    
    # Initialize injector
    injector = MockDataInjector()
    
    if not injector.initialize():
        logger.error("Cannot proceed without Elasticsearch connection")
        sys.exit(1)
    
    # Inject mock data
    errors_injected, errors_failed = injector.inject_mock_data()
    
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

