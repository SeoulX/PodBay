#!/usr/bin/env python3
"""
Script to get the latest error from Elasticsearch and analyze its structure.
"""

import json
import os
from elasticsearch import Elasticsearch

# Load configuration from environment
elasticsearch_host = os.getenv("ELASTICSEARCH_HOST", "http://es-v4.media-meter.in:80")
elasticsearch_username = os.getenv("ELASTICSEARCH_USERNAME", "elastic")
elasticsearch_password = os.getenv("ELASTICSEARCH_PASSWORD", "")

# Connect to Elasticsearch
es_config = {
    "hosts": [elasticsearch_host],
    "verify_certs": False,
    "ssl_show_warn": False,
    "request_timeout": 30
}

if elasticsearch_username and elasticsearch_password:
    es_config["basic_auth"] = (elasticsearch_username, elasticsearch_password)

es = Elasticsearch(**es_config)

print("=" * 80)
print("Fetching Latest 2 Errors from Elasticsearch")
print("=" * 80)
print(f"Host: {elasticsearch_host}\n")

# Query for the latest 2 errors
query = {
    "query": {
        "term": {
            "processor.event": "error"
        }
    },
    "size": 2,
    "sort": [{"@timestamp": {"order": "desc"}}]
}

try:
    response = es.search(index="logs-apm.error*", body=query)
    
    total_hits = response.get("hits", {}).get("total", {}).get("value", 0)
    print(f"Total errors in index: {total_hits}\n")
    
    if total_hits == 0:
        print("No errors found in Elasticsearch.")
        exit(0)
    
    hits = response.get("hits", {}).get("hits", [])
    if not hits:
        print("No error documents returned.")
        exit(0)
    
    # Process each error
    for idx, error_doc in enumerate(hits, 1):
        source = error_doc.get("_source", {})
        
        print("=" * 80)
        print(f"ERROR #{idx} - FULL JSON STRUCTURE")
        print("=" * 80)
        print(json.dumps(source, indent=2, default=str))
    
    print("\n" + "=" * 80)
    print("ERROR STRUCTURE ANALYSIS")
    print("=" * 80)
    
    # Analyze the structure
    print("\n1. TOP-LEVEL FIELDS:")
    for key in source.keys():
        print(f"   - {key}")
    
    # Error information
    error_info = source.get("error", {})
    if error_info:
        print("\n2. ERROR OBJECT STRUCTURE:")
        print(f"   error:")
        for key in error_info.keys():
            value = error_info.get(key)
            if isinstance(value, dict):
                print(f"     - {key}: (object)")
                for subkey in value.keys():
                    print(f"       - {subkey}")
            else:
                print(f"     - {key}: {type(value).__name__}")
    
    # Service information
    service_info = source.get("service", {})
    if service_info:
        print("\n3. SERVICE OBJECT STRUCTURE:")
        print(f"   service:")
        for key in service_info.keys():
            print(f"     - {key}")
    
    # Extract specific fields
    print("\n" + "=" * 80)
    print("EXTRACTED ERROR INFORMATION")
    print("=" * 80)
    
    # Error type
    error_type = error_info.get("type", "N/A")
    print(f"\nError Type Path: error.type")
    print(f"Error Type Value: {error_type}")
    
    # Error message - try multiple paths
    error_message = None
    error_message_path = None
    
    # Try error.log.message first
    error_log = error_info.get("log", {})
    if error_log and error_log.get("message"):
        error_message = error_log.get("message")
        error_message_path = "error.log.message"
    # Try error.message
    elif error_info.get("message"):
        error_message = error_info.get("message")
        error_message_path = "error.message"
    # Try error.exception.message
    elif error_info.get("exception", {}).get("message"):
        error_message = error_info.get("exception", {}).get("message")
        error_message_path = "error.exception.message"
    
    print(f"\nError Message Path: {error_message_path or 'NOT FOUND'}")
    if error_message:
        print(f"Error Message Value (first 500 chars):")
        print(f"  {error_message[:500]}")
        if len(error_message) > 500:
            print(f"  ... (truncated, total length: {len(error_message)} chars)")
    else:
        print("Error Message Value: NOT FOUND")
        print("\nAvailable error fields:")
        print(json.dumps(error_info, indent=2, default=str)[:1000])
    
    # Error culprit
    error_culprit = error_info.get("culprit", "N/A")
    print(f"\nError Culprit Path: error.culprit")
    print(f"Error Culprit Value: {error_culprit}")
    
    # Service and environment
    service_name = service_info.get("name", "N/A")
    environment = service_info.get("environment", "N/A")
    print(f"\nService Name Path: service.name")
    print(f"Service Name Value: {service_name}")
    print(f"\nEnvironment Path: service.environment")
    print(f"Environment Value: {environment}")
    
    # Timestamp
    timestamp = source.get("@timestamp", "N/A")
    print(f"\nTimestamp Path: @timestamp")
    print(f"Timestamp Value: {timestamp}")
    
    # Kubernetes pod name
    kubernetes = source.get("kubernetes", {})
    pod_name = "N/A"
    if kubernetes:
        pod_info = kubernetes.get("pod", {})
        if pod_info:
            pod_name = pod_info.get("name", "N/A")
            print(f"\nPod Name Path: kubernetes.pod.name")
            print(f"Pod Name Value: {pod_name}")
    
    # Save to file
    output_file = "latest_error_structure.json"
    with open(output_file, "w") as f:
        json.dump({
            "full_structure": source,
            "extracted_fields": {
                "error_type": error_type,
                "error_type_path": "error.type",
                "error_message": error_message,
                "error_message_path": error_message_path,
                "error_culprit": error_culprit,
                "error_culprit_path": "error.culprit",
                "service_name": service_name,
                "service_name_path": "service.name",
                "environment": environment,
                "environment_path": "service.environment",
                "timestamp": timestamp,
                "timestamp_path": "@timestamp",
                "pod_name": pod_name,
                "pod_name_path": "kubernetes.pod.name"
            }
        }, f, indent=2, default=str)
    
    print(f"\n" + "=" * 80)
    print(f"Full structure saved to: {output_file}")
    print("=" * 80)
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

