#!/usr/bin/env python3
"""
Test script to query Elasticsearch and check for APM errors.
Uses the same configuration as the monitor.
"""

import sys
import os
from apm_monitor.config import Config
from apm_monitor.elasticsearch_client import ElasticsearchClient
from apm_monitor.queries import APMErrorQueries

def load_config_from_files():
    """Load configuration from config.properties and secret.properties files."""
    config = {}
    
    # Load config.properties
    if os.path.exists('config.properties'):
        with open('config.properties', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    
    # Load secret.properties
    if os.path.exists('secret.properties'):
        with open('secret.properties', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    
    # Set environment variables
    for key, value in config.items():
        os.environ[key] = value
    
    return config

def main():
    print("=" * 60)
    print("Testing Elasticsearch Connection and Query")
    print("=" * 60)
    
    # Load configuration from files
    print("\n1. Loading configuration from files...")
    config_dict = load_config_from_files()
    
    # Create config object
    config = Config()
    
    print(f"   Elasticsearch Host: {config.elasticsearch_host}")
    print(f"   Username: {config.elasticsearch_username or 'Not set'}")
    print(f"   Password: {'*' * len(config.elasticsearch_password) if config.elasticsearch_password else 'Not set'}")
    print(f"   Service Filter: {config.service_name or 'All services'}")
    print(f"   Environment Filter: {config.environment or 'All environments'}")
    print(f"   Lookback Minutes: {config.lookback_minutes}")
    
    # Initialize Elasticsearch client
    print("\n2. Connecting to Elasticsearch...")
    es_client = ElasticsearchClient(config)
    
    if not es_client.check_connection():
        print("   ❌ FAILED: Cannot connect to Elasticsearch")
        print("   Please check your connection settings and credentials.")
        sys.exit(1)
    
    print("   ✅ Connected successfully!")
    
    # Initialize queries
    print("\n3. Querying for APM errors...")
    queries = APMErrorQueries(es_client.get_client())
    
    errors_by_service_env, total_errors = queries.query_errors_by_service_env(
        config.service_name,
        config.environment,
        config.lookback_minutes
    )
    
    if errors_by_service_env is None:
        print("   ❌ FAILED: Query returned an error")
        sys.exit(1)
    
    # Display results
    print("\n4. Results:")
    print("=" * 60)
    
    if total_errors == 0:
        print("   ✅ No errors detected in the last {} minutes".format(config.lookback_minutes))
    else:
        print(f"   ⚠️  Found {total_errors} total errors across {len(errors_by_service_env)} service/environment combinations")
        print("\n   Breakdown by Service/Environment:")
        print("-" * 60)
        for error_info in errors_by_service_env:
            if error_info["error_count"] > 0:
                print(f"   • {error_info['service']} ({error_info['environment']}): {error_info['error_count']} errors")
    
    print("=" * 60)
    print("\n✅ Test completed successfully!")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

