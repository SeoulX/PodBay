"""
Elasticsearch query module.
Handles all queries related to APM error data.
"""

import logging
from elasticsearch.exceptions import RequestError

logger = logging.getLogger(__name__)


class APMErrorQueries:
    
    def __init__(self, es_client):
        self.es_client = es_client
    
    def query_errors_by_service_env(self, service_name, environment, lookback_minutes):
        try:
            filters = [
                {"term": {"processor.event": "error"}},
                {"range": {"@timestamp": {"gte": f"now-{lookback_minutes}m"}}}
            ]
            
            if service_name:
                filters.append({"term": {"service.name": service_name}})
                logger.info(f"Filtering by service: {service_name}")
            else:
                logger.info("Querying all services")
            
            if environment:
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
                "size": 0,
                "aggs": {
                    "by_service": {
                        "terms": {
                            "field": "service.name",
                            "size": 1000,
                            "missing": "unknown"
                        },
                        "aggs": {
                            "by_environment": {
                                "terms": {
                                    "field": "service.environment",
                                    "size": 100,
                                    "missing": "unknown"
                                },
                                "aggs": {
                                    "sample_errors": {
                                        "top_hits": {
                                            "size": 3,
                                            "sort": [{"@timestamp": {"order": "desc"}}],
                                            "_source": {
                                                "includes": [
                                                    "error",
                                                    "@timestamp",
                                                    "kubernetes.pod.name",
                                                    "message"
                                                ]
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
            res = self.es_client.search(
                index="logs-apm.error*",
                body=query_body
            )
            
            errors_by_service_env = []
            total_errors = 0
            
            if "aggregations" in res and "by_service" in res["aggregations"]:
                for service_bucket in res["aggregations"]["by_service"]["buckets"]:
                    service = service_bucket["key"]
                    service_total = service_bucket["doc_count"]
                    
                    if "by_environment" in service_bucket:
                        for env_bucket in service_bucket["by_environment"]["buckets"]:
                            env = env_bucket["key"]
                            env_count = env_bucket["doc_count"]
                            
                            sample_errors = []
                            if "sample_errors" in env_bucket:
                                for hit in env_bucket["sample_errors"]["hits"]["hits"]:
                                    error_source = hit.get("_source", {})
                                    error_info = error_source.get("error", {})
                                    error_log = error_info.get("log", {})
                                    
                                    # Extract error message - try multiple paths
                                    # 1. For log-based errors: error.log.message
                                    error_message = error_log.get("message", "")
                                    # 2. For exception-based errors: error.exception[0].message
                                    if not error_message:
                                        error_exception = error_info.get("exception", [])
                                        if error_exception and len(error_exception) > 0:
                                            error_message = error_exception[0].get("message", "")
                                    # 3. Top-level message field
                                    if not error_message:
                                        error_message = error_source.get("message", "")
                                    # 4. Fallback to error type or grouping name
                                    if not error_message:
                                        error_message = error_info.get("grouping_name", "")
                                    # 5. Last resort fallback
                                    if not error_message:
                                        error_message = "Unknown error"
                                        logger.warning(f"Could not extract error message from error structure")
                                    
                                    if len(error_message) > 500:
                                        error_message = error_message[:500] + "..."
                                    
                                    # Extract error type - try multiple paths
                                    # 1. For exception-based errors: error.exception[0].type
                                    error_type = ""
                                    error_exception = error_info.get("exception", [])
                                    if error_exception and len(error_exception) > 0:
                                        error_type = error_exception[0].get("type", "")
                                    # 2. For log-based errors: error.log.logger_name
                                    if not error_type:
                                        error_type = error_log.get("logger_name", "")
                                    # 3. Fallback to grouping_name
                                    if not error_type:
                                        error_type = error_info.get("grouping_name", "Log Error")
                                    
                                    # Extract culprit
                                    error_culprit = error_info.get("culprit", "")
                                    
                                    # Extract pod name
                                    pod_name = ""
                                    kubernetes = error_source.get("kubernetes", {})
                                    if kubernetes:
                                        pod_info = kubernetes.get("pod", {})
                                        pod_name = pod_info.get("name", "")
                                    
                                    sample_errors.append({
                                        "message": error_message,
                                        "culprit": error_culprit,
                                        "type": error_type,
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

