"""
Elasticsearch query module.
Handles all queries related to APM error data.
"""

import logging
from elasticsearch.exceptions import RequestError

logger = logging.getLogger(__name__)


class APMErrorQueries:
    """Class for querying APM errors from Elasticsearch."""
    
    def __init__(self, es_client):
        """
        Initialize APM error queries.
        
        Args:
            es_client: Elasticsearch client instance
        """
        self.es_client = es_client
    
    def query_errors_by_service_env(self, service_name, environment, lookback_minutes):
        """
        Query Elasticsearch for APM errors grouped by service and environment.
        
        Args:
            service_name: Optional service name filter (None for all services)
            environment: Optional environment filter (None for all environments)
            lookback_minutes: Number of minutes to look back for errors
        
        Returns:
            tuple: (errors_by_service_env list, total_errors count) or (None, None) on error
        """
        try:
            # Build query filters
            filters = [
                {"term": {"processor.event": "error"}},
                {"range": {"@timestamp": {"gte": f"now-{lookback_minutes}m"}}}
            ]
            
            # Add service filter if specified
            if service_name:
                # Try keyword field first, fallback to text field
                filters.append({"term": {"service.name": service_name}})
                logger.info(f"Filtering by service: {service_name}")
            else:
                logger.info("Querying all services")
            
            # Add environment filter if specified
            if environment:
                # Try keyword field first, fallback to text field
                filters.append({"term": {"service.environment": environment}})
                logger.info(f"Filtering by environment: {environment}")
            else:
                logger.info("Querying all environments")
            
            query_body = {
                "query": {
                    "bool": {
                        "filter": filters
                    }
                },
                "size": 0,  # We don't need the actual documents
                "aggs": {
                    "by_service": {
                        "terms": {
                            "field": "service.name",  # Use keyword field for aggregations (logs-apm.error* uses keyword type)
                            "size": 1000,  # Support up to 1000 services
                            "missing": "unknown"  # Handle missing values
                        },
                        "aggs": {
                            "by_environment": {
                                "terms": {
                                    "field": "service.environment",  # Use keyword field for aggregations (logs-apm.error* uses keyword type)
                                    "size": 100,  # Support up to 100 environments per service
                                    "missing": "unknown"  # Handle missing values
                                },
                                "aggs": {
                                    "sample_errors": {
                                        "top_hits": {
                                            "size": 3,
                                            "sort": [{"@timestamp": {"order": "desc"}}],
                                            "_source": {
                                                "includes": ["error.log.message", "error.culprit", "error.type", "@timestamp", "kubernetes.pod.name"]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            
            logger.info(f"Querying APM errors in last {lookback_minutes} minutes")
            # Query both apm-* and logs-apm.error* indices to catch all error types
            res = self.es_client.search(
                index="logs-apm.error*",
                body=query_body
            )
            
            # Parse aggregation results
            errors_by_service_env = []
            total_errors = 0
            
            if "aggregations" in res and "by_service" in res["aggregations"]:
                for service_bucket in res["aggregations"]["by_service"]["buckets"]:
                    service = service_bucket["key"]
                    service_total = service_bucket["doc_count"]
                    
                    # Get environment breakdown
                    if "by_environment" in service_bucket:
                        for env_bucket in service_bucket["by_environment"]["buckets"]:
                            env = env_bucket["key"]
                            env_count = env_bucket["doc_count"]
                            
                            # Extract sample error messages
                            sample_errors = []
                            if "sample_errors" in env_bucket:
                                for hit in env_bucket["sample_errors"]["hits"]["hits"]:
                                    error_source = hit.get("_source", {})
                                    error_info = error_source.get("error", {})
                                    error_log = error_info.get("log", {})
                                    
                                    error_message = error_log.get("message", "")
                                    if not error_message:
                                        error_message = error_info.get("message", "")
                                    if not error_message:
                                        error_message = error_info.get("type", "Unknown error")
                                    
                                    # Truncate long messages
                                    if len(error_message) > 500:
                                        error_message = error_message[:500] + "..."
                                    
                                    # Extract pod name if available
                                    pod_name = ""
                                    kubernetes = error_source.get("kubernetes", {})
                                    if kubernetes:
                                        pod_info = kubernetes.get("pod", {})
                                        pod_name = pod_info.get("name", "")
                                    
                                    sample_errors.append({
                                        "message": error_message,
                                        "culprit": error_info.get("culprit", ""),
                                        "type": error_info.get("type", ""),
                                        "timestamp": error_source.get("@timestamp", ""),
                                        "pod_name": pod_name
                                    })
                            
                            errors_by_service_env.append({
                                "service": service,
                                "environment": env,
                                "error_count": env_count,
                                "sample_errors": sample_errors
                            })
                            total_errors += env_count
                    else:
                        # No environment field, use "unknown"
                        errors_by_service_env.append({
                            "service": service,
                            "environment": "unknown",
                            "error_count": service_total,
                            "sample_errors": []
                        })
                        total_errors += service_total
            
            logger.info(
                f"Found {total_errors} total errors across "
                f"{len(errors_by_service_env)} service/environment combinations"
            )
            
            return errors_by_service_env, total_errors
        except RequestError as e:
            logger.error(f"Elasticsearch query error: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Unexpected error querying Elasticsearch: {e}")
            return None, None

