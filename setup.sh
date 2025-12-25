#!/bin/bash

# Kasparro ETL System - Setup Script
# This script helps set up the development environment

set -e

echo "=================================="
echo "Kasparro ETL System - Setup"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
echo -n "Checking Docker installation... "
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}✗ Docker not found${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
echo -n "Checking Docker Compose installation... "
if command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}✗ Docker Compose not found${NC}"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if .env file exists
echo -n "Checking .env file... "
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ Found${NC}"
else
    echo -e "${YELLOW}✗ Not found${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env file${NC}"
    echo ""
    echo -e "${YELLOW}⚠ IMPORTANT: Please edit .env and add your API keys:${NC}"
    echo "  - COINPAPRIKA_API_KEY"
    echo "  - COINGECKO_API_KEY"
    echo ""
    echo "Press Enter after you've added your API keys..."
    read
fi

# Check API keys
echo "Checking API keys in .env..."
source .env

if [ -z "$COINPAPRIKA_API_KEY" ] || [ "$COINPAPRIKA_API_KEY" = "your_coinpaprika_api_key_here" ]; then
    echo -e "${YELLOW}⚠ WARNING: COINPAPRIKA_API_KEY not set${NC}"
    echo "Get your API key from: https://coinpaprika.com/api"
fi

if [ -z "$COINGECKO_API_KEY" ] || [ "$COINGECKO_API_KEY" = "your_coingecko_api_key_here" ]; then
    echo -e "${YELLOW}⚠ Note: COINGECKO_API_KEY not set (optional - has free tier)${NC}"
    echo "Get your API key from: https://www.coingecko.com/en/api"
fi

echo ""
echo "Setup complete! You can now start the system with:"
echo "  make up"
echo ""
echo "Once started, you can access:"
echo "  - API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Health: http://localhost:8000/health"
echo ""
echo "Run tests with:"
echo "  make test"
echo ""
echo "Run smoke tests with:"
echo "  ./smoke_test.sh"
echo ""
