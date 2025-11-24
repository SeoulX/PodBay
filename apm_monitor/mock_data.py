"""
Mock data injection module.
Handles injecting test APM error data into Elasticsearch.
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from elasticsearch.exceptions import ConnectionError, RequestError
from apm_monitor.config import Config
from apm_monitor.elasticsearch_client import ElasticsearchClient

logger = logging.getLogger(__name__)


class MockDataInjector:
    """Class for injecting mock APM error data."""
    
    def __init__(self, config=None):
        """
        Initialize mock data injector.
        
        Args:
            config: Optional Config object (creates new one if not provided)
        """
        self.config = config or Config()
        self.es_client = None
    
    def initialize(self):
        """
        Initialize Elasticsearch client.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        # Initialize Elasticsearch client
        self.es_client = ElasticsearchClient(self.config)
        
        # Check connection
        if not self.es_client.check_connection():
            logger.error("Cannot proceed without Elasticsearch connection")
            return False
        
        return True
    
    def generate_mock_error_document(self, service_name, environment, timestamp):
        """
        Generate a mock APM error document.
        
        Args:
            service_name: Name of the service
            environment: Environment name
            timestamp: Timestamp for the error
        
        Returns:
            dict: Mock error document
        """
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
    
    def inject_mock_data(self, num_errors=None, services=None, environments=None):
        """
        Inject mock APM error data into Elasticsearch.
        
        Args:
            num_errors: Number of errors to inject (uses config if None)
            services: List of service names (uses config if None)
            environments: List of environment names (uses config if None)
        
        Returns:
            tuple: (errors_injected count, errors_failed count)
        """
        num_errors = num_errors or self.config.num_errors
        services = services or self.config.services
        environments = environments or self.config.environments
        
        logger.info(
            f"Injecting {num_errors} mock errors across "
            f"{len(services)} services and {len(environments)} environments"
        )
        
        # Calculate time range - errors in the last 5 minutes
        now = datetime.now(timezone.utc)
        time_range_minutes = 5
        
        errors_injected = 0
        errors_failed = 0
        es = self.es_client.get_client()
        
        for i in range(num_errors):
            # Randomly select service and environment
            service = random.choice(services)
            environment = random.choice(environments)
            
            # Generate timestamp within the last 5 minutes
            minutes_ago = random.uniform(0, time_range_minutes)
            timestamp = now - timedelta(minutes=minutes_ago)
            
            # Generate mock error document
            doc = self.generate_mock_error_document(service, environment, timestamp)
            
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
                    logger.debug(
                        f"Injected error {i+1}/{num_errors}: {service}/{environment} "
                        f"at {timestamp.isoformat()}"
                    )
                else:
                    errors_failed += 1
                    logger.warning(f"Failed to inject error {i+1}/{num_errors}")
                    
            except Exception as e:
                errors_failed += 1
                logger.error(f"Error injecting document {i+1}: {e}")
        
        logger.info(
            f"Injection complete: {errors_injected} succeeded, {errors_failed} failed"
        )
        return errors_injected, errors_failed

