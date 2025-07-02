#!/bin/bash

echo "Setting up Triage Agent System..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "Please edit .env and add your Google API key"
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker first."
    exit 1
fi

# Start PostgreSQL
echo "Starting PostgreSQL database..."
docker run -d --name postgres-triage \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=triage_agent_db \
  -p 5432:5432 \
  postgres:15-alpine

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 5

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Setup complete! You can now run:"
echo "  python main.py          # Start the API server"
echo "  python example_usage.py # Run example usage"
echo "  python test_jsonb.py    # Test JSONB functionality"