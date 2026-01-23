# AI Secretary Examples

This directory contains example scripts and configurations for using AI Secretary.

## Quick Start

1. **Set up your environment:**
   ```bash
   # Copy the example environment file to the project root
   cp ../.env.example ../.env
   
   # Edit .env and add your JIRA credentials
   nano ../.env
   ```

2. **Generate your first daily plan:**
   ```bash
   # From the project root
   ./examples/generate-plan.sh
   ```

3. **Save plan to a file:**
   ```bash
   ./examples/generate-plan.sh -o daily-plan.md
   ```

4. **Include previous day's closure rate:**
   ```bash
   # If you completed 2 out of 3 tasks yesterday (67% closure rate)
   ./examples/generate-plan.sh --closure-rate 0.67
   ```

## Direct CLI Usage

You can also use the `ai-secretary` command directly:

```bash
# Make sure environment variables are set
export JIRA_BASE_URL='https://your-company.atlassian.net'
export JIRA_EMAIL='your-email@company.com'
export JIRA_API_TOKEN='your-api-token'

# Generate plan
ai-secretary generate-plan

# Or with options
ai-secretary generate-plan -o plan.md --closure-rate 0.67
```

## Configuration Options

### Required Environment Variables

- `JIRA_BASE_URL` - Your JIRA instance URL
- `JIRA_EMAIL` - Your JIRA account email
- `JIRA_API_TOKEN` - Your JIRA API token (generate at https://id.atlassian.com/manage-profile/security/api-tokens)

### Optional Environment Variables

- `ADMIN_TIME_START` - Start time for admin block (default: 14:00)
- `ADMIN_TIME_END` - End time for admin block (default: 15:30)

## Example Output

```markdown
# Daily Plan - 2026-01-23

## Previous Day
- Closure Rate: 2/3 tasks completed (67%)

## Today's Priorities

1. **[PROJ-123] Implement user authentication**
   - Effort: 8.0 hours
   - Type: Story
   - Priority: High

2. **[PROJ-124] Fix login bug**
   - Effort: 4.0 hours
   - Type: Bug

## Administrative Block (14:00-15:30)

- [ ] [PROJ-126] Email responses
- [ ] [PROJ-127] Weekly report

## Other Active Tasks (For Reference)

- [PROJ-129] Waiting on external team (blocked by dependencies)
- [PROJ-130] Multi-day feature (decomposition needed)
```

## Tips

- Run the plan generator at the start of your workday
- Use the closure rate to track your daily progress
- Review "Other Active Tasks" to see what's blocked or needs decomposition
- The admin block is scheduled during low-energy periods (post-lunch by default)
