"""JIRA API helpers for fetching bug reports."""

import os

import requests


SAMPLE_BUG_REPORT = """
Bug Title: BUG-001: User Authority Verification Failure
Bug ID: SCRUM-5
Reporter: shinu n
Environment: Production
Severity (Reporter): Critical

Steps to Reproduce:
- Login as Viewer role user.
- Navigate to Administration → User Management.
- Edit an existing user profile.
- Save changes.

Actual Result: System allows user modifications without validating authority.
Expected Result: Viewer users should have read-only access and should not be able to modify user information.

Additional Info:
- During validation of role-based access control, users assigned with "Viewer" role were able to access the User Management page and perform edit operations.
- Environment : QA Environment, Build 5.2.1
"""


def _extract_atlassian_text(node):
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        return "".join(_extract_atlassian_text(child) for child in node.get("content", []))
    if isinstance(node, list):
        return "".join(_extract_atlassian_text(item) for item in node)
    return ""


def fetch_jira_ticket(bug_id):
    jira_email = os.getenv("JIRA_EMAIL")
    jira_token = os.getenv("JIRA_API_TOKEN")
    jira_base_url = os.getenv("JIRA_BASE_URL", "https://shinulearning1.atlassian.net").rstrip("/")

    if not jira_email or not jira_token:
        print("❌ JIRA_EMAIL or JIRA_API_TOKEN is missing. Using sample bug report instead.")
        return None

    try:
        url = f"{jira_base_url}/rest/api/3/issue/{bug_id}"
        r = requests.get(
            url,
            auth=(jira_email, jira_token),
            headers={"Accept": "application/json"},
            params={"fields": "summary,description,reporter"},
            timeout=10,
        )
        if r.status_code == 404:
            print(f"❌ JIRA issue {bug_id} not found at {jira_base_url}. Using sample bug report instead.")
            return None
        if r.status_code in (401, 403):
            print(f"❌ JIRA authentication failed (status {r.status_code}). Check JIRA_EMAIL/JIRA_API_TOKEN. Using sample bug report instead.")
            print("Response:", r.text)
            return None

        r.raise_for_status()
        data = r.json()
        f = data.get("fields", {})

        desc = _extract_atlassian_text(f.get("description", {})).strip() or "No description provided"
        reporter = f.get("reporter", {}).get("displayName", "Unknown")
        summary = f.get("summary", "No title provided")

        return f"""Bug Title: {summary}
Bug ID: {data.get('key', bug_id)}
Reporter: {reporter}

{desc}"""
    except requests.exceptions.Timeout:
        print("❌ JIRA API request timed out. Using sample bug report instead.")
        return None
    except ValueError as ve:
        print(f"❌ Failed to decode JIRA response: {ve}. Using sample bug report instead.")
        print("Response body:", getattr(r, 'text', 'n/a'))
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ JIRA request failed: {e}. Using sample bug report instead.")
        return None
    except Exception as e:
        print(f"❌ Unexpected error fetching JIRA ticket: {e}. Using sample bug report instead.")
        return None
