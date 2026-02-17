# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

# Docker Local Stack - Quick Start

## ✅ Stack is Ready!

Your local Docker environment is now running and replicating the AWS serverless stack.

## 🚀 Services Running

- **API**: http://localhost:8000 (FastAPI + Lambda handlers)
- **Logs Viewer**: http://localhost:8080 (Dozzle - real-time logs)
- **Scheduler**: Running in background (cron: 7 AM weekdays)

## 📋 Quick Commands

### Check Status
```bash
docker-compose ps
```

### View Logs
```bash
# API logs
docker-compose logs -f api

# Scheduler logs
docker-compose logs -f scheduler

# All logs
docker-compose logs -f

# Or open browser: http://localhost:8080
```

### Generate JWT Token
```bash
# Using script
./scripts/docker-local.sh token admin 30

# Or direct curl
curl -X POST "http://localhost:8000/api/v1/auth/token?user_id=admin&expiry_days=30"
```

### Test API
```bash
# Health check (no auth)
curl http://localhost:8000/api/v1/health

# Generate plan (requires token)
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/token?user_id=admin&expiry_days=1" | jq -r .token)

curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-02-17"}' \
  http://localhost:8000/api/v1/plan | jq .
```

### Stop/Start Stack
```bash
# Stop
docker-compose down

# Start
docker-compose up -d

# Restart
docker-compose restart

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

## 🔧 Using the Helper Script

The `scripts/docker-local.sh` script provides convenient commands:

```bash
# Start stack
./scripts/docker-local.sh up

# Stop stack
./scripts/docker-local.sh down

# View logs
./scripts/docker-local.sh logs api

# Generate token
./scripts/docker-local.sh token admin 30

# Run tests
./scripts/docker-local.sh test

# Rebuild
./scripts/docker-local.sh rebuild

# Clean up
./scripts/docker-local.sh clean
```

## 📊 Monitoring

### Real-time Logs (Browser)
Open http://localhost:8080 to see logs from all containers in real-time.

### API Health
```bash
curl http://localhost:8000/api/v1/health
```

### Check Scheduler Status
```bash
docker-compose logs scheduler | grep "Next scheduled run"
```

## 🧪 Testing

### Automated Test Suite
```bash
# Using script
./scripts/docker-local.sh test

# Or directly
python examples/test_local_stack.py
```

### Manual Testing
```bash
# 1. Generate token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/token?user_id=admin&expiry_days=1" | jq -r .token)

# 2. Test endpoints
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/plan/2026-02-17
```

## 🐛 Troubleshooting

### Services Not Starting
```bash
# Check logs
docker-compose logs

# Rebuild images
docker-compose build --no-cache
docker-compose up -d
```

### Port Already in Use
Edit `docker-compose.yml` and change ports:
```yaml
ports:
  - "8001:8000"  # Use 8001 instead of 8000
```

### JIRA Connection Issues
```bash
# Check environment variables
docker-compose exec api env | grep JIRA

# Test JIRA connection
docker-compose exec api python examples/diagnose-jira-connection.py
```

### Clear Everything and Start Fresh
```bash
./scripts/docker-local.sh clean
./scripts/docker-local.sh up
```

## 📝 Configuration

### Environment Variables
Edit `.env` file:
```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token
JWT_SECRET=your-secret-here
SCHEDULE_CRON=0 7 * * 1-5
LOG_LEVEL=DEBUG
```

After changing `.env`, restart:
```bash
docker-compose restart
```

### Scheduler Configuration
Change cron schedule in `.env`:
```bash
# Every day at 8 AM
SCHEDULE_CRON=0 8 * * *

# Every 30 minutes (for testing)
SCHEDULE_CRON=*/30 * * * *
```

## 🔄 Development Workflow

1. **Make code changes** in `triage/` or `lambda/`
2. **Restart services** to pick up changes:
   ```bash
   docker-compose restart api
   ```
3. **View logs** to debug:
   ```bash
   docker-compose logs -f api
   ```
4. **Test changes**:
   ```bash
   ./scripts/docker-local.sh test
   ```

## 📚 Next Steps

1. **Test locally**: Verify all endpoints work
2. **Debug issues**: Use logs and shell access
3. **Deploy to AWS**: Once tested, deploy with `./scripts/deploy.sh dev`

## 📖 Documentation

- [Full Docker Setup Guide](docs/DOCKER_LOCAL_SETUP.md)
- [AWS Deployment Guide](docs/AWS_DEPLOYMENT.md)
- [Main README](README.md)

## 🆘 Need Help?

1. Check logs: `docker-compose logs`
2. Verify environment: `docker-compose exec api env`
3. Test JIRA: `python examples/diagnose-jira-connection.py`
4. Review documentation in `docs/`

---

**Stack Status**: ✅ Running
**API**: http://localhost:8000
**Logs**: http://localhost:8080
