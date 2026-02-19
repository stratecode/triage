#!/bin/bash
# TrIAge
# Copyright (C) 2026 StrateCode
# Licensed under the GNU Affero General Public License v3 (AGPLv3)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${GREEN}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if .env file exists
if [ ! -f .env ]; then
    print_warning ".env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        print_info "Created .env file. Please edit it with your JIRA credentials."
        exit 1
    else
        print_error ".env.example not found!"
        exit 1
    fi
fi

# Parse command
COMMAND=${1:-up}

case $COMMAND in
    up)
        print_info "Starting TrIAge local stack..."
        docker compose -p triage up -d
        
        print_info "Waiting for LocalStack initialization..."
        echo "This may take a minute while Lambda functions are deployed..."
        
        print_info "Waiting for API Gateway proxy to be ready..."
        sleep 5
        
        print_info "Checking service health..."
        docker compose -p triage ps
        
        echo ""
        print_info "✅ TrIAge local stack is running!"
        echo ""
        echo "📍 API URL: http://localhost:8000"
        echo "📍 LocalStack: http://localhost:4566"
        echo "📊 Logs Viewer: http://localhost:8080"
        echo ""
        echo "🔍 Check API Gateway status:"
        echo "   curl http://localhost:8000/health"
        echo ""
        echo "📋 View logs:"
        echo "   docker compose -p triage logs -f api"
        echo "   docker compose -p triage logs -f localstack-init"
        echo "   docker compose -p triage logs -f localstack"
        echo ""
        echo "🧪 Test the API:"
        echo "   make docker-test"
        echo ""
        ;;
    
    down)
        print_info "Stopping TrIAge local stack..."
        docker compose -p triage down
        print_info "✅ Stack stopped"
        ;;
    
    restart)
        print_info "Restarting TrIAge local stack..."
        docker compose -p triage restart
        print_info "✅ Stack restarted"
        ;;
    
    logs)
        SERVICE=${2:-api}
        print_info "Showing logs for $SERVICE..."
        docker compose logs -f $SERVICE
        ;;
    
    build)
        print_info "Building Docker images..."
        docker compose -p triage build --no-cache
        print_info "✅ Build complete"
        ;;
    
    rebuild)
        print_info "Rebuilding and restarting..."
        docker compose -p triage down
        docker compose -p triage build --no-cache
        docker compose -p triage up -d
        print_info "✅ Rebuild complete"
        ;;
    
    test)
        print_info "Testing API endpoints..."
        
        # Check if API is running
        if ! curl -s http://localhost:8000/health > /dev/null; then
            print_error "API is not running. Start it with: make docker-up"
            exit 1
        fi
        
        print_info "Checking API Gateway status..."
        curl -s http://localhost:8000/health | jq .
        
        # Test health endpoint
        print_info "Testing /api/v1/health..."
        curl -s http://localhost:8000/api/v1/health | jq .
        
        # Test plan generation (this will fail without auth, but tests the routing)
        print_info "Testing /api/v1/plan (expect 401 without auth)..."
        curl -s -X POST \
            -H "Content-Type: application/json" \
            -d '{"date":"'$(date +%Y-%m-%d)'"}' \
            http://localhost:8000/api/v1/plan | jq .
        
        print_info "✅ Basic connectivity tests complete"
        print_info "Note: Full API tests require proper authentication setup in Lambda"
        ;;
    
    token)
        print_warning "Token generation is now handled by Lambda functions in LocalStack"
        print_info "Authentication needs to be implemented in the Lambda handlers"
        print_info "For now, you can test endpoints without authentication"
        ;;
    
    clean)
        print_info "Cleaning up Docker resources..."
        docker compose -p triage down -v
        docker system prune -f
        rm -rf logs/*
        print_info "✅ Cleanup complete"
        ;;
    
    shell)
        SERVICE=${2:-api}
        print_info "Opening shell in $SERVICE container..."
        docker compose exec $SERVICE /bin/bash
        ;;
    
    *)
        echo "TrIAge Local Docker Stack Manager"
        echo ""
        echo "Usage: $0 [command] [options]"
        echo ""
        echo "Commands:"
        echo "  up              Start the stack (default)"
        echo "  down            Stop the stack"
        echo "  restart         Restart the stack"
        echo "  logs [service]  Show logs (default: api)"
        echo "  build           Build Docker images"
        echo "  rebuild         Rebuild and restart"
        echo "  test            Run API tests"
        echo "  token [user] [days]  Generate JWT token (default: admin, 30 days)"
        echo "  clean           Clean up all resources"
        echo "  shell [service] Open shell in container (default: api)"
        echo ""
        echo "Examples:"
        echo "  $0 up"
        echo "  $0 logs api"
        echo "  $0 token admin 7"
        echo "  $0 test"
        ;;
esac
