# JIRA API Migration - Error 410 Fix

## Problem

Starting in 2024, Atlassian deprecated the `/rest/api/3/search` endpoint and replaced it with `/rest/api/3/search/jql`. Applications using the old endpoint receive a **HTTP 410 Gone** error.

## Error Message

```
HTTP 410 Gone
La API solicitada se ha eliminado. Migra a la API /rest/api/3/search/jql.
```

## Solution

The AI Secretary has been updated to use the new endpoint:

- **Old (deprecated)**: `/rest/api/3/search`
- **New (current)**: `/rest/api/3/search/jql`

## Changes Made

### 1. Updated JIRA Client (`ai_secretary/jira_client.py`)

The `_fetch_with_api_version()` method now uses the correct endpoint:

```python
if api_version == 3:
    endpoint = f"{self.base_url}/rest/api/3/search/jql"
else:
    endpoint = f"{self.base_url}/rest/api/2/search"
```

### 2. Added Fallback Support

If API v3 fails with a 410 error, the client automatically tries API v2 as a fallback for older JIRA instances.

### 3. Improved Error Handling

Added specific handling for HTTP 410 errors with helpful error messages.

## Diagnostic Tool

A diagnostic script is available to test your JIRA connection:

```bash
python examples/diagnose-jira-connection.py
```

This script will:
1. Check environment variables
2. Validate base URL format
3. Test authentication
4. Test the search endpoint
5. Provide detailed error messages if something fails

## Testing

After the fix, you can verify the connection works:

```bash
# Run diagnostic
python examples/diagnose-jira-connection.py

# Generate a plan
ai-secretary generate-plan
```

## References

- [Atlassian Developer Changelog #CHANGE-2046](https://developer.atlassian.com/changelog/#CHANGE-2046)
- [JIRA Cloud REST API v3 Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)

## Migration Timeline

- **Before 2024**: `/rest/api/3/search` was the standard endpoint
- **2024**: Atlassian deprecated the old endpoint
- **Current**: `/rest/api/3/search/jql` is the required endpoint

## Compatibility

The updated client is compatible with:
- ✅ JIRA Cloud (latest)
- ✅ JIRA Cloud (with new API)
- ✅ JIRA Server/Data Center (API v2 fallback)

## Troubleshooting

If you still get errors after updating:

1. **Run the diagnostic tool**:
   ```bash
   python examples/diagnose-jira-connection.py
   ```

2. **Check your JIRA instance type**:
   - JIRA Cloud: Should use API v3 with `/search/jql`
   - JIRA Server/Data Center: May need API v2

3. **Verify credentials**:
   - Ensure your API token is valid
   - Check that your email is correct
   - Confirm the base URL is correct

4. **Check JIRA permissions**:
   - You need permission to search for issues
   - Your API token must have appropriate scopes
