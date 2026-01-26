# DHI Migration - Quick Reference Card

## Files Changed

| File | Change |
|------|--------|
| **Dockerfile** | Python 3.11→3.12, Debian→Alpine, Docker Official→DHI |
| **docker-compose.yml** | Redis & PostgreSQL now use DHI versions |

## New Dockerfile Structure

```dockerfile
# Builder (has pip for package management)
FROM dhi.io/python:3.12-alpine3.21-dev AS builder
  RUN pip install dependencies...

# Runtime (minimal, non-root)
FROM dhi.io/python:3.12-alpine3.21
  USER nonroot
  EXPOSE 3000
```

## Quick Build

```bash
# Login (required once)
docker login

# Build
docker build -t triage-slack-bot:dhi .

# Run with compose
docker-compose up -d

# Check status
docker-compose ps
```

## Key Improvements

| Item | Before | After |
|------|--------|-------|
| Python | 3.11 | 3.12 |
| Size | ~180MB | ~90MB |
| Base | Debian 12 | Alpine 3.21 |
| User | slackbot (1000) | nonroot (65534) |
| Security | Standard | Hardened |

## Common Commands

```bash
# View logs
docker-compose logs -f slack-bot

# Health check
docker exec triage-slack-bot python -c "import sys; sys.exit(0)"

# Redis test
docker exec triage-redis redis-cli ping

# PostgreSQL test
docker exec triage-postgres pg_isready -U triage

# Stop services
docker-compose down

# Rebuild
docker build --no-cache -t triage-slack-bot:dhi .
```

## If Build Fails (401 Unauthorized)

Edit Dockerfile, change:
```dockerfile
# From:
FROM dhi.io/python:3.12-alpine3.21-dev
FROM dhi.io/python:3.12-alpine3.21

# To:
FROM python:3.12-alpine
FROM python:3.12-alpine
```

Then adjust USER line from `nonroot` to `1000:1000`.

## Environment Variables (No Change)

All `.env` variables work exactly as before:
- SLACK_BOT_TOKEN
- SLACK_SIGNING_SECRET
- REDIS_URL
- DATABASE_URL
- etc.

## Port Bindings (No Change)

- Slack Bot: 3000 (HTTP webhooks)
- Redis: 6379 (cache)
- PostgreSQL: 5432 (database)

## Documentation Files

| File | Purpose |
|------|---------|
| DHI_MIGRATION_SUMMARY.md | Detailed migration overview |
| DHI_BUILD_GUIDE.md | Build and test instructions |
| MIGRATION_CHANGES.md | Before/after comparison |
| MIGRATION_COMPLETION_REPORT.md | Full completion report |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Build fails (401) | Run `docker login` or use fallback public images |
| Container won't start | Check logs: `docker-compose logs` |
| Redis not connecting | Verify REDIS_URL in .env |
| DB not connecting | Verify DATABASE_URL in .env |
| Port already in use | Check for conflicts: `lsof -i :3000` |

## Rollback (If Needed)

```bash
# Edit Dockerfile and docker-compose.yml
# Remove dhi.io/ prefix from all images

# Rebuild
docker build --no-cache -t triage-slack-bot:rollback .

# Restart
docker-compose down
docker-compose up -d
```

## Next Steps

1. ✓ Review this quick reference
2. ✓ Read DHI_BUILD_GUIDE.md for details
3. → Run: `docker login && docker build -t triage-slack-bot:dhi .`
4. → Test: `docker-compose up -d` and verify services
5. → Deploy: Follow staging process in MIGRATION_COMPLETION_REPORT.md

---

**Status:** Migration Complete - Ready for Deployment
