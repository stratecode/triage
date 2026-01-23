# Using .env for Configuration

The AI Secretary automatically loads environment variables from a `.env` file in the project root. This makes configuration simple and secure.

## Quick Start

1. **Copy the example file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit your `.env` file**:
   ```bash
   # Required: JIRA Configuration
   JIRA_BASE_URL=https://your-company.atlassian.net
   JIRA_EMAIL=your-email@company.com
   JIRA_API_TOKEN=your-api-token-here
   
   # Optional: Project Filter
   # Only show tasks from this specific project
   JIRA_PROJECT=MYPROJ
   
   # Optional: Admin Block Scheduling
   ADMIN_TIME_START=14:00
   ADMIN_TIME_END=15:30
   ```

3. **Run the application**:
   ```bash
   ai-secretary generate-plan
   ```

That's it! The application automatically loads your configuration from `.env`.

## How It Works

The application uses the `python-dotenv` library to automatically load environment variables from the `.env` file when the CLI starts. This happens transparently - you don't need to:

- Manually `source .env`
- Export environment variables
- Pass configuration as command-line arguments

## Security Best Practices

1. **Never commit `.env` to version control**
   - The `.env` file is already in `.gitignore`
   - It contains sensitive credentials (API tokens)

2. **Use `.env.example` as a template**
   - Commit `.env.example` with placeholder values
   - Team members can copy it to create their own `.env`

3. **Rotate API tokens regularly**
   - Generate new JIRA API tokens periodically
   - Update your `.env` file with the new token

## Generating a JIRA API Token

1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a descriptive name (e.g., "AI Secretary")
4. Copy the token and paste it into your `.env` file

## Troubleshooting

### "JIRA_BASE_URL environment variable is required"

This means the `.env` file wasn't found or doesn't contain the required variables. Check:

1. The `.env` file exists in the project root
2. The file contains all required variables
3. Variable names are spelled correctly (case-sensitive)

### "Authentication Error"

This usually means:

1. Your JIRA_EMAIL is incorrect
2. Your JIRA_API_TOKEN is invalid or expired
3. Your JIRA_BASE_URL is incorrect

Double-check all values in your `.env` file.

## Alternative: Environment Variables

If you prefer not to use a `.env` file, you can still set environment variables manually:

```bash
export JIRA_BASE_URL=https://your-company.atlassian.net
export JIRA_EMAIL=your-email@company.com
export JIRA_API_TOKEN=your-api-token

ai-secretary generate-plan
```

The application will use these environment variables if they're set, even without a `.env` file.
