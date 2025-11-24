"""
Elasticsearch client module.
Handles Elasticsearch connection, client creation, and connection checks.
"""

import logging
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, RequestError

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """Elasticsearch client wrapper."""
    
    def __init__(self, config):
        """
        Initialize Elasticsearch client.
        
        Args:
            config: Config object with Elasticsearch settings
        """
        self.config = config
        self.client = None
        self._create_client()
    
    def _create_client(self):
        """Create Elasticsearch client from configuration."""
        es_config = self.config.get_elasticsearch_config()
        self.client = Elasticsearch(**es_config)
    
    def check_connection(self):
        """
        Check if Elasticsearch is accessible.
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            # Try to get cluster info instead of ping (more reliable)
            info = self.client.info()
            if info:
                logger.info(
                    f"Successfully connected to Elasticsearch cluster: "
                    f"{info.get('cluster_name', 'unknown')}"
                )
                return True
            else:
                logger.error("Failed to get Elasticsearch info")
                return False
        except (ConnectionError, RequestError) as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            # Try ping as fallback
            try:
                if self.client.ping():
                    logger.info("Successfully connected to Elasticsearch (via ping)")
                    return True
            except Exception:
                pass
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Elasticsearch: {e}")
            return False
    
    def get_client(self):
        """
        Get the Elasticsearch client instance.
        
        Returns:
            Elasticsearch: The Elasticsearch client
        """
        return self.client

