#!/bin/bash
# Quick update script for Fantasy Football Astro site

set -e

echo "=================================="
echo "Fantasy Football Site Update"
echo "=================================="
echo ""

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "✓ Virtual environment activated"
else
    echo "❌ Virtual environment not found. Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Generate all data
echo ""
echo "Generating data..."
python scripts/generate_data.py

# Check if we should build the site
if [ "$1" = "--build" ]; then
    echo ""
    echo "Building Astro site..."
    cd website
    npm run build
    echo "✓ Site built successfully"
    echo ""
    echo "To preview: cd website && npm run preview"
elif [ "$1" = "--dev" ]; then
    echo ""
    echo "Starting dev server..."
    cd website
    npm run dev
else
    echo ""
    echo "Data updated! Options:"
    echo "  • Run dev server:  ./update.sh --dev"
    echo "  • Build for prod:  ./update.sh --build"
fi
