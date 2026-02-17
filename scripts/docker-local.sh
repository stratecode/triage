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
        docker-compose up -d
        
        print_info "Waiting for services to be ready..."
        sleep 5
        
        print_info "Checking service health..."
        docker-compose ps
        
        echo ""
        print_info "✅ TrIAge local stack is running!"
        echo ""
        echo "📍 API URL: http://localhost:8000"
        echo "📊 Logs Viewer: http://localhost:8080"
        echo ""
        echo "🔑 Generate a JWT token:"
        echo "   curl -X POST http://localhost:8000/api/v1/auth/token?user_id=admin&expiry_days=30"
        echo ""
        echo "📋 View logs:"
        echo "   docker-compose logs -f api"
        echo "   docker-compose logs -f scheduler"
        echo ""
        ;;
    
    down)
        print_info "Stopping TrIAge local stack..."
        docker-compose down
        print_info "✅ Stack stopped"
        ;;
    
    restart)
        print_info "Restarting TrIAge local stack..."
        docker-compose restart
        print_info "✅ Stack restarted"
        ;;
    
    logs)
        SERVICE=${2:-api}
        print_info "Showing logs for $SERVICE..."
        docker-compose logs -f $SERVICE
        ;;
    
    build)
        print_info "Building Docker images..."
        docker-compose build --no-cache
        print_info "✅ Build complete"
        ;;
    
    rebuild)
        print_info "Rebuilding and restarting..."
        docker-compose down
        docker-compose build --no-cache
        docker-compose up -d
        print_info "✅ Rebuild complete"
        ;;
    
    test)
        print_info "Testing API endpoints..."
        
        # Check if API is running
        if ! curl -s http://localhost:8000/api/v1/health > /dev/null; then
            print_error "API is not running. Start it with: ./scripts/docker-local.sh up"
            exit 1
        fi
        
        # Generate token
        print_info "Generating JWT token..."
        TOKEN_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/auth/token?user_id=admin&expiry_days=1")
        TOKEN=$(echo $TOKEN_RESPONSE | grep -o '"token":"[^"]*' | cut -d'"' -f4)
        
        if [ -z "$TOKEN" ]; then
            print_error "Failed to generate token"
            exit 1
        fi
        
        print_info "Token generated: ${TOKEN:0:20}..."
        
        # Test health endpoint
        print_info "Testing /api/v1/health..."
        curl -s http://localhost:8000/api/v1/health | jq .
        
        # Test plan generation
        print_info "Testing /api/v1/plan..."
        curl -s -X POST \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"date":"'$(date +%Y-%m-%d)'"}' \
            http://localhost:8000/api/v1/plan | jq .
        
        print_info "✅ Tests complete"
        ;;
    
    token)
        USER_ID=${2:-admin}
        EXPIRY=${3:-30}
        
        print_info "Generating JWT token for user: $USER_ID (expires in $EXPIRY days)..."
        
        TOKEN_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/auth/token?user_id=$USER_ID&expiry_days=$EXPIRY")
        
        echo ""
        echo "$TOKEN_RESPONSE" | jq .
        echo ""
        
        TOKEN=$(echo $TOKEN_RESPONSE | grep -o '"token":"[^"]*' | cut -d'"' -f4)
        
        if [ ! -z "$TOKEN" ]; then
            print_info "Use this token in your requests:"
            echo "Authorization: Bearer $TOKEN"
        fi
        ;;
    
    clean)
        print_info "Cleaning up Docker resources..."
        docker-compose down -v
        docker system prune -f
        rm -rf logs/*
        print_info "✅ Cleanup complete"
        ;;
    
    shell)
        SERVICE=${2:-api}
        print_info "Opening shell in $SERVICE container..."
        docker-compose exec $SERVICE /bin/bash
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
