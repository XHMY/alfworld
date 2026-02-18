#!/bin/bash
# Quick start script for ALFWorld text-only Docker setup

set -e

echo "=========================================="
echo "ALFWorld Text-Only Docker Setup"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Warning: docker-compose is not installed."
    echo "Install it for easier multi-container management:"
    echo "https://docs.docker.com/compose/install/"
    echo ""
fi

# Set data directory
DATA_DIR="${ALFWORLD_DATA:-$HOME/.cache/alfworld}"

echo "Data directory: $DATA_DIR"
echo ""

# Check if data exists
if [ ! -d "$DATA_DIR" ] || [ -z "$(ls -A $DATA_DIR)" ]; then
    echo "Warning: ALFWorld data not found in $DATA_DIR"
    echo ""
    echo "To download data:"
    echo "  1. Install alfworld: pip install alfworld"
    echo "  2. Run: alfworld-download"
    echo "  3. Or set ALFWORLD_DATA to your data location"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Build Docker image
echo "Building Docker image..."
docker build -f Dockerfile.text -t alfworld-text:latest .

echo ""
echo "=========================================="
echo "Build complete!"
echo "=========================================="
echo ""
echo "Quick start commands:"
echo ""
echo "1. Run interactive shell:"
echo "   docker run -it -v $DATA_DIR:/data:ro alfworld-text:latest bash"
echo ""
echo "2. Run simple example:"
echo "   docker run -v $DATA_DIR:/data:ro alfworld-text:latest python examples/simple_example.py"
echo ""
echo "3. Run parallel environments:"
echo "   docker run -v $DATA_DIR:/data:ro alfworld-text:latest python examples/parallel_envs_example.py --num-envs 4"
echo ""

if command -v docker-compose &> /dev/null; then
    echo "4. Use docker-compose (4 parallel containers):"
    echo "   ALFWORLD_DATA=$DATA_DIR docker-compose up -d"
    echo "   docker-compose exec alfworld-env-1 python examples/simple_example.py"
    echo ""
fi

echo "For more information, see: docker/README_TEXT.md"
echo ""
