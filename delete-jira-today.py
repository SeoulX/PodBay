#!/usr/bin/env python3
"""
Script to delete all Jira issues created today.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from jira import JIRA
from jira.exceptions import JIRAError

def load_config_from_properties():
    """Load configuration from secret.properties file if it exists."""
    config = {}
    props_file = "secret.properties"
    
    if os.path.exists(props_file):
        with open(props_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    
    return config

def main():
    # Load config from properties file or environment variables
    props_config = load_config_from_properties()
    
    jira_url = os.getenv("JIRA_URL") or props_config.get("JIRA_URL")
    jira_email = os.getenv("JIRA_EMAIL") or props_config.get("JIRA_EMAIL")
    jira_api_token = os.getenv("JIRA_API_TOKEN") or props_config.get("JIRA_API_TOKEN")
    jira_project_key = os.getenv("JIRA_PROJECT_KEY") or props_config.get("JIRA_PROJECT_KEY")
    
    # Validate configuration
    if not all([jira_url, jira_email, jira_api_token, jira_project_key]):
        print("Error: Missing required Jira configuration.")
        print("Please set the following environment variables or add them to secret.properties:")
        print("  - JIRA_URL")
        print("  - JIRA_EMAIL")
        print("  - JIRA_API_TOKEN")
        print("  - JIRA_PROJECT_KEY")
        sys.exit(1)
    
    # Connect to Jira
    print(f"Connecting to Jira at {jira_url}...")
    try:
        jira = JIRA(
            server=jira_url,
            basic_auth=(jira_email, jira_api_token)
        )
        print("✓ Connected successfully\n")
    except Exception as e:
        print(f"✗ Failed to connect to Jira: {e}")
        sys.exit(1)
    
    # Get today's date - try both UTC and Philippine Time
    # Jira typically stores dates in UTC
    utc_now = datetime.now(timezone.utc)
    ph_timezone = timezone(timedelta(hours=8))
    ph_now = datetime.now(ph_timezone)
    
    # Use date-only format for JQL (Jira handles timezone conversion)
    today_date_utc = utc_now.strftime("%Y-%m-%d")
    today_date_ph = ph_now.strftime("%Y-%m-%d")
    
    # Try multiple date formats - Jira JQL supports date-only format
    print(f"Searching for issues created today in project {jira_project_key}...")
    print(f"  (UTC date: {today_date_utc}, PH date: {today_date_ph})\n")
    
    try:
        # First try: date-only format (Jira will interpret in server timezone)
        jql = (
            f'project = {jira_project_key} '
            f'AND created >= "{today_date_ph}" '
            f'AND created < "{ph_now + timedelta(days=1):%Y-%m-%d}" '
            f'ORDER BY created DESC'
        )
        
        print(f"JQL query: {jql}\n")
        issues = jira.search_issues(jql, maxResults=100)
        
        # If no results, try with UTC date
        if not issues:
            jql_utc = (
                f'project = {jira_project_key} '
                f'AND created >= "{today_date_utc}" '
                f'AND created < "{utc_now + timedelta(days=1):%Y-%m-%d}" '
                f'ORDER BY created DESC'
            )
            print(f"Trying UTC date format...")
            print(f"JQL query: {jql_utc}\n")
            issues = jira.search_issues(jql_utc, maxResults=100)
        
        # If still no results, try a broader search and filter in Python
        if not issues:
            print("Trying broader search (all recent issues)...")
            jql_broad = (
                f'project = {jira_project_key} '
                f'AND created >= "{ph_now - timedelta(days=1):%Y-%m-%d}" '
                f'ORDER BY created DESC'
            )
            all_recent = jira.search_issues(jql_broad, maxResults=100)
            
            # Filter to today's issues
            issues = []
            for issue in all_recent:
                if hasattr(issue.fields, 'created'):
                    created_str = issue.fields.created
                    # Parse the created date
                    created_date = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                    # Check if it's today in either timezone
                    created_date_utc = created_date.astimezone(timezone.utc).date()
                    created_date_ph = created_date.astimezone(ph_timezone).date()
                    today_utc = utc_now.date()
                    today_ph = ph_now.date()
                    
                    if created_date_utc == today_utc or created_date_ph == today_ph:
                        issues.append(issue)
        
        if not issues:
            print(f"✓ No issues found created today")
            print(f"  (Searched for dates: {today_date_ph} PH time, {today_date_utc} UTC)")
            return
        
        print(f"Found {len(issues)} issue(s) created today:\n")
        for issue in issues:
            summary = issue.fields.summary if hasattr(issue.fields, 'summary') else "N/A"
            created = issue.fields.created[:10] if hasattr(issue.fields, 'created') else "N/A"
            print(f"  - {issue.key}: {summary} (created: {created})")
        
        # Ask for action
        print(f"\nWhat would you like to do with {len(issues)} issue(s)?")
        print(f"  1. Delete (permanently remove)")
        print(f"  2. Close (mark as resolved/closed)")
        response = input("Enter choice (1 or 2): ").strip()
        
        if response == "2":
            action = "close"
            action_verb = "Closing"
        elif response == "1":
            action = "delete"
            action_verb = "Deleting"
        else:
            print("Invalid choice. Cancelled.")
            return
        
        if action == "delete":
            print(f"\n⚠️  WARNING: This will DELETE {len(issues)} issue(s) permanently!")
            confirm = input("Are you sure? (yes/no): ")
            if confirm.lower() not in ['yes', 'y']:
                print("Deletion cancelled.")
                return
        
        # Process issues
        print(f"\n{action_verb} issues...")
        success_count = 0
        failed_count = 0
        permission_error = False
        
        for issue in issues:
            try:
                summary = issue.fields.summary if hasattr(issue.fields, 'summary') else "N/A"
                
                if action == "delete":
                    issue.delete()
                    print(f"  ✓ Deleted {issue.key}: {summary}")
                else:  # close
                    # Try to transition to closed/resolved status
                    # First, get available transitions
                    transitions = jira.transitions(issue)
                    closed_transitions = [t for t in transitions if 'close' in t['name'].lower() or 'resolve' in t['name'].lower() or 'done' in t['name'].lower()]
                    
                    if closed_transitions:
                        # Use the first available close/resolve transition
                        jira.transition_issue(issue, closed_transitions[0]['id'])
                        print(f"  ✓ Closed {issue.key}: {summary}")
                    else:
                        # Try common transition IDs
                        try:
                            jira.transition_issue(issue, '2')  # Common ID for "Close"
                            print(f"  ✓ Closed {issue.key}: {summary}")
                        except:
                            # If that fails, try to set status directly
                            issue.update(fields={'status': {'name': 'Closed'}})
                            print(f"  ✓ Closed {issue.key}: {summary}")
                
                success_count += 1
            except JIRAError as e:
                error_msg = str(e)
                if "403" in error_msg or "permission" in error_msg.lower():
                    permission_error = True
                    action_name = "delete" if action == "delete" else "close"
                    print(f"  ✗ Permission denied for {issue.key}: You do not have permission to {action_name} issues in this project")
                else:
                    action_name = "delete" if action == "delete" else "close"
                    print(f"  ✗ Failed to {action_name} {issue.key}: {e}")
                failed_count += 1
            except Exception as e:
                action_name = "delete" if action == "delete" else "close"
                print(f"  ✗ Unexpected error {action_name}ing {issue.key}: {e}")
                failed_count += 1
        
        action_past = "Deleted" if action == "delete" else "Closed"
        print(f"\n✓ {action_past} complete!")
        print(f"  - {action_past}: {success_count}")
        print(f"  - Failed: {failed_count}")
        
        if permission_error:
            print(f"\n⚠️  PERMISSION ISSUE DETECTED")
            action_name = "delete" if action == "delete" else "close"
            print(f"Your Jira account does not have permission to {action_name} issues in project {jira_project_key}.")
            print(f"\nOptions:")
            if action == "delete":
                print(f"  1. Ask your Jira admin to grant you 'Delete Issues' permission")
                print(f"  2. Ask your Jira admin to delete these issues manually")
                print(f"  3. Use a Jira account that has delete permissions")
                print(f"  4. Try closing the issues instead (requires less permissions)")
            else:
                print(f"  1. Ask your Jira admin to grant you 'Close Issues' permission")
                print(f"  2. Ask your Jira admin to close these issues manually")
                print(f"  3. Use a Jira account that has close permissions")
            print(f"\nIssue keys that need to be {action_name.lower()}d:")
            for issue in issues:
                print(f"  - {issue.key}")
        
    except JIRAError as e:
        print(f"✗ Error searching for issues: {e}")
        if hasattr(e, 'response'):
            print(f"Response: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

