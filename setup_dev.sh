#!/bin/bash
# Setup script for StreamCondor development environment

set -e

echo "================================================"
echo "StreamCondor Development Environment Setup"
echo "================================================"
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.12"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
  echo "Error: Python 3.12 or higher is required (found $python_version)"
  exit 1
fi
echo "✓ Python $python_version found"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ -d ".venv" ]; then
  echo "Virtual environment already exists, skipping..."
else
  python3 -m venv .venv
  echo "✓ Virtual environment created"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "✓ pip upgraded"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
if [ $? -eq 0 ]; then
  echo "✓ Dependencies installed"
else
  echo "✗ Failed to install dependencies"
  exit 1
fi
echo ""

# Check if streamlink is installed
echo "Checking for streamlink..."
if command -v streamlink &> /dev/null; then
  streamlink_version=$(streamlink --version 2>&1 | head -n1)
  echo "✓ $streamlink_version found"
else
  echo "⚠ streamlink not found in PATH"
  echo "  Install it with: pip install streamlink"
fi
echo ""

# Generate placeholder icons
echo "Generating placeholder icons..."
if [ -f "assets/generate_icons.py" ]; then
  python assets/generate_icons.py
  echo "✓ Icons generated"
else
  echo "⚠ Icon generator not found"
fi
echo ""

echo "================================================"
echo "Setup complete!"
echo "================================================"
echo ""
echo "To start developing:"
echo "  1. Activate the virtual environment:"
echo "     source .venv/bin/activate"
echo ""
echo "  2. Run the application:"
echo "     python src/main.py"
echo ""
echo "  3. Run tests:"
echo "     python test/run_tests.py"
echo ""
echo "For more information, see doc/DEVELOPMENT.md"
echo ""
