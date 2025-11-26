"""
Jira integration module.
Handles creating and managing Jira tickets for APM errors.
"""

import logging
import re
import hashlib
from datetime import datetime, timezone, timedelta
from jira import JIRA
from jira.exceptions import JIRAError

logger = logging.getLogger(__name__)


class JiraClient:
    """Class for interacting with Jira API."""
    
    def __init__(self, jira_url, email, api_token, project_key, issue_type="Bug", 
                 assignee=None, labels=None, components=None):
        """
        Initialize Jira client.
        
        Args:
            jira_url: Jira server URL (e.g., https://yourcompany.atlassian.net)
            email: Email address for Jira authentication
            api_token: Jira API token (from https://id.atlassian.com/manage-profile/security/api-tokens)
            project_key: Jira project key (e.g., "APM")
            issue_type: Type of issue to create (default: "Bug")
            assignee: Optional assignee username or email
            labels: Optional list of labels to add to tickets
            components: Optional list of component names to add to tickets
        """
        self.jira_url = jira_url
        self.email = email
        self.api_token = api_token
        self.project_key = project_key
        self.issue_type = issue_type
        self.assignee = assignee
        self.labels = labels or []
        self.components = components or []
        
        self.jira = None
        self._connect()
    
    def _connect(self):
        """Establish connection to Jira."""
        try:
            self.jira = JIRA(
                server=self.jira_url,
                basic_auth=(self.email, self.api_token)
            )
            logger.info(f"Successfully connected to Jira at {self.jira_url}")
        except JIRAError as e:
            logger.error(f"Failed to connect to Jira: {e}")
            self.jira = None
        except Exception as e:
            logger.error(f"Unexpected error connecting to Jira: {e}")
            self.jira = None
    
    def is_connected(self):
        """Check if Jira connection is active."""
        return self.jira is not None
    
    def _generate_unique_id(self, service_name, environment, today_date):
        """
        Generate a unique identifier for the ticket.
        Format: DO-{hash}-{date}
        
        Args:
            service_name: Name of the service
            environment: Environment name
            today_date: Date string (YYYY-MM-DD)
        
        Returns:
            str: Unique identifier like "DO-112625-112625" (MMDDYY format)
        """
        # Create a hash from service + environment + date
        hash_input = f"{service_name}_{environment}_{today_date}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:6]
        
        # Convert to uppercase and format as number-like string
        # Convert hex to a number and take first 6 digits
        hash_num = str(int(hash_value, 16))[:6].zfill(6)
        
        # Format date as MMDDYY
        # today_date is in YYYY-MM-DD format
        date_parts = today_date.split("-")
        if len(date_parts) == 3:
            year = date_parts[0]
            month = date_parts[1]
            day = date_parts[2]
            # Get last 2 digits of year
            year_short = year[-2:]
            date_formatted = f"{month}{day}{year_short}"
        else:
            # Fallback to original format if parsing fails
            date_formatted = today_date.replace("-", "")
        
        # Format: DO-{6-digit-number}-{MMDDYY}
        unique_id = f"DO-{hash_num}-{date_formatted}"
        
        return unique_id
    
    def _format_error_description(self, service_name, environment, today_error_count, sample_errors, today_date=None, unique_id=None):
        """
        Format error description for Jira ticket.
        
        Args:
            service_name: Name of the service
            environment: Environment name
            today_error_count: Number of errors detected today
            sample_errors: List of sample error details
            today_date: Date string for today (YYYY-MM-DD), if None will use current date
            unique_id: Unique identifier for the ticket (if None, will be generated)
        
        Returns:
            str: Formatted description
        """
        # Philippine Time (UTC+8)
        ph_timezone = timezone(timedelta(hours=8))
        now = datetime.now(ph_timezone)
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S PHT")
        
        if today_date is None:
            today_date = now.strftime("%Y-%m-%d")
        
        # Generate unique identifier if not provided
        if unique_id is None:
            unique_id = self._generate_unique_id(service_name, environment, today_date)
        
        description = f"""
h3. Error Summary

*Unique ID:* {unique_id}
*Service:* {service_name}
*Environment:* {environment}
*Today's Error Count ({today_date}):* {today_error_count}
*Last Updated:* {timestamp}

h3. Sample Errors

"""
        
        if sample_errors and len(sample_errors) > 0:
            # Show only 1 sample error
            err = sample_errors[0]
            error_msg = err.get("message", "")
            error_type = err.get("type", "")
            error_culprit = err.get("culprit", "")
            pod_name = err.get("pod_name", "")
            error_timestamp = err.get("timestamp", "")
            
            description += "h4. Sample Error\n\n"
            
            if pod_name:
                description += f"*Pod:*\n{{code}}\n{pod_name}\n{{code}}\n\n"
            
            # if error_type:
            #     description += f"*Type:*\n{{code}}\n{error_type}\n{{code}}\n\n"
            
            if error_culprit:
                description += f"*Location:*\n{{code}}\n{error_culprit}\n{{code}}\n\n"
            
            # if error_timestamp:
            #     description += f"*Timestamp:* {error_timestamp}\n\n"
            
            if error_msg:
                # Truncate very long messages
                msg = error_msg[:2000] + "..." if len(error_msg) > 2000 else error_msg
                description += f"*Error Message:*\n{{code}}\n{msg}\n{{code}}\n\n"
        else:
            description += "No sample errors available.\n"
        
        description += f"""
h3. Next Steps

Please investigate the errors in the APM dashboard and take appropriate action.

*Note:* This ticket was automatically created by the APM Error Monitor.
"""
        
        return description
    
    def _create_issue_fields(self, service_name, environment, error_count, sample_errors):
        """
        Create issue fields dictionary for Jira ticket.
        
        Args:
            service_name: Name of the service
            environment: Environment name
            error_count: Number of errors
            sample_errors: List of sample error details
        
        Returns:
            dict: Issue fields
        """
        # Get today's date
        ph_timezone = timezone(timedelta(hours=8))
        today_date = datetime.now(ph_timezone).strftime("%Y-%m-%d")
        
        # Generate unique identifier
        unique_id = self._generate_unique_id(service_name, environment, today_date)
        summary = f"[{environment.upper()}] {service_name}: {error_count} APM Error(s) [{unique_id}]"
        
        # Try to get issue type ID, fall back to name
        issue_type_field = {"name": self.issue_type}
        try:
            # Try to get issue type metadata to find the ID
            project_meta = self.jira.createmeta(
                projectKeys=self.project_key,
                issuetypeNames=[self.issue_type],
                expand="projects.issuetypes"
            )
            if project_meta and 'projects' in project_meta and len(project_meta['projects']) > 0:
                project_data = project_meta['projects'][0]
                if 'issuetypes' in project_data and len(project_data['issuetypes']) > 0:
                    issue_type_id = project_data['issuetypes'][0].get('id')
                    if issue_type_id:
                        issue_type_field = {"id": issue_type_id}
                        logger.debug(f"Using issue type ID: {issue_type_id} for '{self.issue_type}'")
        except Exception as e:
            logger.debug(f"Could not get issue type ID, using name: {e}")
            # Fall back to using name
        
        # Get today's date for the description
        ph_timezone = timezone(timedelta(hours=8))
        today_date = datetime.now(ph_timezone).strftime("%Y-%m-%d")
        
        # Generate unique identifier (already in summary, but generate again for description)
        unique_id = self._generate_unique_id(service_name, environment, today_date)
        
        fields = {
            "project": {"key": self.project_key},
            "summary": summary,
            "description": self._format_error_description(service_name, environment, error_count, sample_errors, today_date=today_date, unique_id=unique_id),
            "issuetype": issue_type_field
        }
        
        # Add assignee if specified
        if self.assignee:
            try:
                # Try to find user by username or email
                user = self.jira.search_users(self.assignee)
                if user:
                    fields["assignee"] = {"accountId": user[0].accountId}
                else:
                    logger.warning(f"Could not find Jira user: {self.assignee}")
            except Exception as e:
                logger.warning(f"Error setting assignee {self.assignee}: {e}")
        
        # Add labels - include unique_id as a label for easy searching
        labels_list = list(self.labels) if self.labels else []
        if unique_id not in labels_list:
            labels_list.append(unique_id)
        if labels_list:
            fields["labels"] = labels_list
        
        # Add components
        if self.components:
            component_list = []
            for component_name in self.components:
                try:
                    # Try to find component in project
                    components = self.jira.project_components(self.project_key)
                    component = next((c for c in components if c.name == component_name), None)
                    if component:
                        component_list.append({"id": component.id})
                    else:
                        logger.warning(f"Component '{component_name}' not found in project {self.project_key}")
                except Exception as e:
                    logger.warning(f"Error finding component {component_name}: {e}")
            
            if component_list:
                fields["components"] = component_list
        
        return fields
    
    def find_existing_issue(self, service_name, environment, lookback_hours=24):
        """
        Check if an issue already exists for this service/environment combination.
        
        Args:
            service_name: Name of the service
            environment: Environment name
            lookback_hours: How many hours back to search for existing issues
        
        Returns:
            Issue object if found, None otherwise
        """
        if not self.jira:
            return None
        
        try:
            # Get today's date to generate unique ID
            ph_timezone = timezone(timedelta(hours=8))
            today_date = datetime.now(ph_timezone).strftime("%Y-%m-%d")
            unique_id = self._generate_unique_id(service_name, environment, today_date)
            
            # First, try to search by unique ID as a label (most reliable and fastest)
            # Escape special characters in unique_id for JQL
            unique_id_escaped = unique_id.replace('"', '\\"')
            jql_by_label = (
                f'project = {self.project_key} '
                f'AND labels = "{unique_id_escaped}" '
                f'ORDER BY created DESC'
            )
            
            try:
                issues_by_label = self.jira.search_issues(jql_by_label, maxResults=5)
                if issues_by_label:
                    issue = issues_by_label[0]
                    # Verify the unique_id is actually in the labels
                    issue_labels = list(issue.fields.labels) if hasattr(issue.fields, 'labels') and issue.fields.labels else []
                    if unique_id in issue_labels:
                        logger.info(f"Found existing issue by unique ID label {unique_id} (Jira: {issue.key})")
                        return issue
                    else:
                        logger.debug(f"Found issue by label search but unique_id {unique_id} not in labels: {issue_labels}")
            except Exception as e:
                logger.debug(f"Search by unique ID label failed, trying summary search: {e}")
            
            # Try searching in summary
            try:
                jql_by_id = (
                    f'project = {self.project_key} '
                    f'AND summary ~ "{unique_id_escaped}" '
                    f'ORDER BY created DESC'
                )
                issues_by_id = self.jira.search_issues(jql_by_id, maxResults=5)
                if issues_by_id:
                    issue = issues_by_id[0]
                    # Verify the unique_id is actually in the summary
                    issue_summary = issue.fields.summary
                    if unique_id in issue_summary:
                        logger.info(f"Found existing issue by unique ID in summary {unique_id} (Jira: {issue.key})")
                        return issue
                    else:
                        logger.debug(f"Found issue by summary search but unique_id {unique_id} not in summary: {issue_summary}")
            except Exception as e:
                logger.debug(f"Search by unique ID in summary failed, trying description search: {e}")
            
            # Also try searching in description
            try:
                jql_by_desc = (
                    f'project = {self.project_key} '
                    f'AND description ~ "{unique_id_escaped}" '
                    f'ORDER BY created DESC'
                )
                issues_by_desc = self.jira.search_issues(jql_by_desc, maxResults=5)
                if issues_by_desc:
                    issue = issues_by_desc[0]
                    logger.info(f"Found existing issue by unique ID in description {unique_id} (Jira: {issue.key})")
                    return issue
            except Exception as e:
                logger.debug(f"Search by unique ID in description failed: {e}")
            
            # Fallback: Search for issues created TODAY for this service/environment
            # This is important - we want to find tickets from today even if they don't have the unique_id yet
            ph_timezone = timezone(timedelta(hours=8))
            today_date = datetime.now(ph_timezone).strftime("%Y-%m-%d")
            today_start = f"{today_date}T00:00:00"
            today_end = f"{today_date}T23:59:59"
            
            jql = (
                f'project = {self.project_key} '
                f'AND summary ~ "{service_name}" '
                f'AND summary ~ "{environment}" '
                f'AND created >= "{today_start}" '
                f'AND created <= "{today_end}" '
                f'ORDER BY created DESC'
            )
            
            try:
                issues = self.jira.search_issues(jql, maxResults=10)
                
                # Check if any issue matches closely (same service and environment)
                for issue in issues:
                    summary = issue.fields.summary
                    if service_name.lower() in summary.lower() and environment.lower() in summary.lower():
                        # Extract unique_id from the issue
                        description = issue.fields.description if hasattr(issue.fields, 'description') else ""
                        extracted_unique_id = self._extract_unique_id(description, summary)
                        
                        # If the extracted unique_id matches today's unique_id, this is the right ticket
                        if extracted_unique_id == unique_id:
                            logger.info(f"Found existing issue by unique ID match: {extracted_unique_id} (Jira: {issue.key}) - {summary}")
                            return issue
                        # If no unique_id found but service/env matches and it's from today, it's likely the same ticket
                        elif not extracted_unique_id:
                            logger.info(f"Found issue from today without unique_id: {issue.key}, will update with unique_id {unique_id}")
                            return issue
                        
                        # If unique_id exists but doesn't match, continue searching
                        if extracted_unique_id and extracted_unique_id != unique_id:
                            logger.debug(f"Found issue with different unique_id {extracted_unique_id} (expected {unique_id}), continuing search")
                            continue
            except Exception as e:
                logger.debug(f"Fallback search failed: {e}")
            
            # If we get here, no matching issue was found
            logger.debug(f"No existing issue found for unique_id {unique_id} (service: {service_name}, env: {environment})")
            return None
            
            return None
        except JIRAError as e:
            logger.error(f"Error searching for existing Jira issues: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error searching for existing issues: {e}")
            return None
    
    def create_issue(self, service_name, environment, error_count, sample_errors=None, 
                     check_duplicates=True, duplicate_lookback_hours=24):
        """
        Create a Jira issue for APM errors.
        
        Args:
            service_name: Name of the service
            environment: Environment name
            error_count: Number of errors detected
            sample_errors: Optional list of sample error details
            check_duplicates: Whether to check for existing issues before creating
            duplicate_lookback_hours: Hours to look back when checking for duplicates
        
        Returns:
            Issue object if created successfully, None otherwise
        """
        if not self.jira:
            logger.error("Cannot create Jira issue: not connected to Jira")
            return None
        
        # Check for existing issues if requested
        if check_duplicates:
            # Generate today's unique_id for logging
            ph_timezone = timezone(timedelta(hours=8))
            today_date = datetime.now(ph_timezone).strftime("%Y-%m-%d")
            expected_unique_id = self._generate_unique_id(service_name, environment, today_date)
            logger.info(f"Searching for existing issue with unique_id: {expected_unique_id} (service: {service_name}, env: {environment})")
            
            existing = self.find_existing_issue(service_name, environment, duplicate_lookback_hours)
            if existing:
                # Get the issue creation date
                issue_created_date = existing.fields.created[:10]  # Get YYYY-MM-DD from ISO format
                
                # Extract unique_id from existing issue
                existing_summary = existing.fields.summary if hasattr(existing.fields, 'summary') else ""
                existing_description = existing.fields.description if hasattr(existing.fields, 'description') else ""
                existing_unique_id = self._extract_unique_id(existing_description, existing_summary)
                
                # Also check the description for today's date
                existing_today_count = self._extract_today_error_count(existing_description, today_date)
                
                logger.info(
                    f"Found existing issue {existing.key} (created: {issue_created_date}, "
                    f"unique_id: {existing_unique_id or 'none'}, today's count: {existing_today_count})"
                )
                
                # If unique_id matches OR issue is from today OR has today's count in description, update it
                if (existing_unique_id == expected_unique_id) or (issue_created_date == today_date) or (existing_today_count > 0):
                    logger.info(
                        f"Updating existing issue {existing.key} (unique_id: {existing_unique_id or expected_unique_id}) "
                        f"with {error_count} new errors"
                    )
                    return self.update_existing_issue(
                        existing, 
                        service_name, 
                        environment, 
                        error_count, 
                        sample_errors or []
                    )
                else:
                    # Issue is from a different day - create a new ticket
                    logger.info(
                        f"Existing issue {existing.key} is from {issue_created_date} (unique_id: {existing_unique_id}), "
                        f"but today is {today_date} (expected unique_id: {expected_unique_id}). Creating new ticket for today."
                    )
                    # Continue to create new issue below
            else:
                logger.info(f"No existing issue found for unique_id {expected_unique_id}, will create new ticket")
        
        try:
            # Generate unique_id for logging
            ph_timezone = timezone(timedelta(hours=8))
            today_date = datetime.now(ph_timezone).strftime("%Y-%m-%d")
            unique_id = self._generate_unique_id(service_name, environment, today_date)
            
            fields = self._create_issue_fields(service_name, environment, error_count, sample_errors or [])
            issue = self.jira.create_issue(fields=fields)
            logger.info(
                f"Successfully created Jira issue {unique_id} (Jira: {issue.key}) for {service_name}/{environment}: "
                f"{error_count} errors"
            )
            return issue
        except JIRAError as e:
            logger.error(f"Failed to create Jira issue for {service_name}/{environment}: {e}")
            if hasattr(e, 'response'):
                logger.error(f"Response: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating Jira issue for {service_name}/{environment}: {e}")
            logger.exception(e)
            return None
    
    def _extract_unique_id(self, description, summary):
        """
        Extract unique ID from ticket description or summary.
        
        Args:
            description: Current issue description
            summary: Current issue summary
        
        Returns:
            str: Unique ID if found, None otherwise
        """
        # Try to extract from description first
        if description:
            # Pattern: *Unique ID:* DO-XXXXXX-MMDDYY
            pattern1 = r"Unique ID:\s*DO-(\d+-\d+)"
            match = re.search(pattern1, description, re.IGNORECASE)
            if match:
                unique_id = f"DO-{match.group(1)}"
                logger.debug(f"Extracted unique ID from description: {unique_id}")
                return unique_id
        
        # Try to extract from summary
        if summary:
            # Pattern: [ENV] Service: X errors [DO-XXXXXX-MMDDYY]
            pattern2 = r"\[DO-(\d+-\d+)\]"
            match = re.search(pattern2, summary)
            if match:
                unique_id = f"DO-{match.group(1)}"
                logger.debug(f"Extracted unique ID from summary: {unique_id}")
                return unique_id
        
        return None
    
    def _extract_today_error_count(self, description, today_date):
        """
        Extract today's error count from the description.
        
        Args:
            description: Current issue description
            today_date: Today's date string (YYYY-MM-DD)
        
        Returns:
            int: Today's error count, or 0 if not found or different date
        """
        if not description:
            logger.debug("No description found to extract error count from")
            return 0
        
        # Try multiple patterns to find the error count
        # Pattern 1: "Today's Error Count (YYYY-MM-DD): X"
        pattern1 = rf"Today's Error Count \({today_date}\):\s*(\d+)"
        match = re.search(pattern1, description, re.IGNORECASE)
        if match:
            count = int(match.group(1))
            logger.debug(f"Extracted today's error count: {count} using pattern 1")
            return count
        
        # Pattern 2: "Today's Error Count (YYYY-MM-DD):* X" (with asterisk for Jira formatting)
        pattern2 = rf"Today's Error Count \({today_date}\):\*\s*(\d+)"
        match = re.search(pattern2, description, re.IGNORECASE)
        if match:
            count = int(match.group(1))
            logger.debug(f"Extracted today's error count: {count} using pattern 2")
            return count
        
        # Pattern 3: Look for any date with error count (in case date format differs)
        pattern3 = r"Today's Error Count \([^)]+\):\s*(\d+)"
        match = re.search(pattern3, description, re.IGNORECASE)
        if match:
            # Check if the date matches today
            date_match = re.search(r"Today's Error Count \(([^)]+)\):", description, re.IGNORECASE)
            if date_match and date_match.group(1) == today_date:
                count = int(match.group(1))
                logger.debug(f"Extracted today's error count: {count} using pattern 3")
                return count
        
        logger.warning(f"Could not extract error count from description. Today's date: {today_date}")
        logger.debug(f"Description snippet: {description[:200]}...")
        return 0
    
    def update_existing_issue(self, issue, service_name, environment, new_error_count, sample_errors):
        """
        Update an existing Jira issue with today's error count and add a comment with latest error.
        
        Args:
            issue: Existing Jira issue object
            service_name: Name of the service
            environment: Environment name
            new_error_count: New error count detected in this check
            sample_errors: List of sample error details
        
        Returns:
            Issue object if updated successfully, None otherwise
        """
        if not self.jira:
            logger.error("Cannot update issue: not connected to Jira")
            return None
        
        try:
            # Refresh issue to get latest data
            issue = self.jira.issue(issue.key)
            
            # Get today's date
            ph_timezone = timezone(timedelta(hours=8))
            now = datetime.now(ph_timezone)
            today_date = now.strftime("%Y-%m-%d")
            
            # Extract current today's error count from description
            current_description = issue.fields.description if hasattr(issue.fields, 'description') else ""
            today_error_count = self._extract_today_error_count(current_description, today_date)
            
            logger.info(
                f"Current today's error count from description: {today_error_count}, "
                f"new errors in this check: {new_error_count}"
            )
            
            # If it's a different day or no count found, reset to new count
            # Otherwise, add the new errors to today's count
            if today_error_count == 0:
                # New day or first update - use the new count
                today_error_count = new_error_count
                logger.info(f"Setting today's error count to {today_error_count} (new day or first update)")
            else:
                # Same day - add new errors to today's total
                old_count = today_error_count
                today_error_count += new_error_count
                logger.info(f"Adding {new_error_count} to existing count {old_count} = {today_error_count}")
            
            # Generate unique identifier
            unique_id = self._generate_unique_id(service_name, environment, today_date)
            
            # Update summary with today's error count
            new_summary = f"[{environment.upper()}] {service_name}: {today_error_count} APM Error(s) [{unique_id}]"
            
            # Update description with today's total error count
            new_description = self._format_error_description(
                service_name, 
                environment, 
                today_error_count, 
                sample_errors,
                today_date=today_date,
                unique_id=unique_id
            )
            
            # Update summary and description first
            try:
                # Update summary and description together
                # Log what we're trying to update for debugging
                logger.debug(f"Updating issue {issue.key} with summary length: {len(new_summary)}, description length: {len(new_description)}")
                
                issue.update(
                    summary=new_summary,
                    description=new_description
                )
                logger.info(f"Updated summary and description of {unique_id} (Jira: {issue.key}) to show {today_error_count} errors today ({today_date})")
                
                # Update labels separately if needed
                try:
                    current_labels = list(issue.fields.labels) if hasattr(issue.fields, 'labels') and issue.fields.labels else []
                    labels_changed = False
                    
                    # Add unique_id to labels if not already present
                    if unique_id not in current_labels:
                        current_labels.append(unique_id)
                        labels_changed = True
                    
                    # Also add any configured labels
                    if self.labels:
                        for label in self.labels:
                            if label not in current_labels:
                                current_labels.append(label)
                                labels_changed = True
                    
                    # Only update labels if they changed
                    if labels_changed and current_labels:
                        issue.update(labels=current_labels)
                        logger.debug(f"Updated labels for {unique_id} (Jira: {issue.key}): {current_labels}")
                except Exception as label_error:
                    logger.warning(f"Failed to update labels for {issue.key}, but summary/description were updated: {label_error}")
                
                # Verify the update by reading back the description
                issue = self.jira.issue(issue.key)  # Refresh to get updated data
                updated_description = issue.fields.description if hasattr(issue.fields, 'description') else ""
                verified_count = self._extract_today_error_count(updated_description, today_date)
                if verified_count != today_error_count:
                    logger.warning(
                        f"Description update verification failed! Expected {today_error_count}, "
                        f"but extracted {verified_count} from updated description"
                    )
                else:
                    logger.debug(f"Description update verified: {verified_count} errors")
            except JIRAError as e:
                logger.error(f"Error updating issue description: {e}")
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    logger.error(f"Jira API response: {e.response.text}")
                # Try updating just the summary if description update fails
                try:
                    issue.update(summary=new_summary)
                    logger.info(f"Updated summary only due to description update error")
                except Exception as e2:
                    logger.error(f"Failed to update summary as well: {e2}")
            except Exception as e:
                logger.error(f"Unexpected error updating issue: {e}")
                logger.exception(e)
                # Try updating just the summary if description update fails
                try:
                    issue.update(summary=new_summary)
                    logger.info(f"Updated summary only due to unexpected error")
                except Exception as e2:
                    logger.error(f"Failed to update summary as well: {e2}")
            
            # Format comment with latest error details
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S PHT")
            
            comment = f"*Latest Error Detected*\n\n"
            comment += f"*Errors in this check:* {new_error_count}\n"
            comment += f"*Today's Total ({today_date}):* {today_error_count}\n"
            comment += f"*Detected At:* {timestamp}\n\n"
            
            if sample_errors and len(sample_errors) > 0:
                err = sample_errors[0]
                error_msg = err.get("message", "")
                error_type = err.get("type", "")
                error_culprit = err.get("culprit", "")
                pod_name = err.get("pod_name", "")
                error_timestamp = err.get("timestamp", "")
                
                comment += "h4. Latest Error Details\n\n"
                
                if pod_name:
                    comment += f"*Pod:*\n{{code}}\n{pod_name}\n{{code}}\n\n"
                
                # if error_type:
                #     comment += f"*Type:*\n{{code}}\n{error_type}\n{{code}}\n\n"
                
                if error_culprit:
                    comment += f"*Location:*\n{{code}}\n{error_culprit}\n{{code}}\n\n"
                
                # if error_timestamp:
                #     comment += f"*Timestamp:* {error_timestamp}\n\n"
                
                if error_msg:
                    msg = error_msg[:2000] + "..." if len(error_msg) > 2000 else error_msg
                    comment += f"*Error Message:*\n{{code}}\n{msg}\n{{code}}\n\n"
            
            # Add comment to the issue
            self.jira.add_comment(issue, comment)
            logger.info(f"Added comment to {unique_id} (Jira: {issue.key}) with latest error details")
            
            return issue
            
        except JIRAError as e:
            logger.error(f"Failed to update Jira issue {issue.key}: {e}")
            if hasattr(e, 'response'):
                logger.error(f"Response: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error updating Jira issue {issue.key}: {e}")
            logger.exception(e)
            return None
    
    def add_comment(self, issue_key, comment):
        """
        Add a comment to an existing Jira issue.
        
        Args:
            issue_key: Jira issue key (e.g., "APM-123")
            comment: Comment text
        
        Returns:
            bool: True if comment added successfully, False otherwise
        """
        if not self.jira:
            logger.error("Cannot add comment: not connected to Jira")
            return False
        
        try:
            issue = self.jira.issue(issue_key)
            self.jira.add_comment(issue, comment)
            logger.info(f"Successfully added comment to {issue_key}")
            return True
        except JIRAError as e:
            logger.error(f"Failed to add comment to {issue_key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error adding comment to {issue_key}: {e}")
            return False

