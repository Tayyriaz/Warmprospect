#!/bin/bash
# Quick start script for Docker Compose deployment

set -e

echo "🚀 Starting GoAccel Chatbot Platform with Docker Compose..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env file. Please edit it with your actual values!"
        echo "   Required: GEMINI_API_KEY, ADMIN_API_KEY"
        exit 1
    else
        echo "❌ .env.example not found. Please create .env file manually."
        exit 1
    fi
fi

# Validate docker-compose.yml
echo "📋 Validating docker-compose.yml..."
docker-compose config > /dev/null 2>&1 || {
    echo "❌ docker-compose.yml validation failed!"
    exit 1
}

# Build and start services
echo "🔨 Building and starting services..."
docker-compose up -d --build

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check service status
echo ""
echo "📊 Service Status:"
docker-compose ps

# Check health endpoint
echo ""
echo "🏥 Checking health endpoint..."
sleep 10
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Application is healthy!"
else
    echo "⚠️  Health check failed. Check logs with: docker-compose logs -f app"
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Useful commands:"
echo "  View logs:        docker-compose logs -f app"
echo "  Stop services:    docker-compose stop"
echo "  Restart:          docker-compose restart"
echo "  Full cleanup:     docker-compose down -v"
