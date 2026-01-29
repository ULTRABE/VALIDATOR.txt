#!/bin/bash
# Quick Start Script for Login Validator

echo "🔐 Real Account Login Validator - Quick Start"
echo "=============================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo "✅ Dependencies installed"
echo ""

# Check if credentials file exists and has content
if [ ! -f "credentials.txt" ]; then
    echo "❌ credentials.txt not found!"
    exit 1
fi

# Count non-comment, non-empty lines
CRED_COUNT=$(grep -v '^#' credentials.txt | grep -v '^$' | grep ':' | wc -l)

if [ $CRED_COUNT -eq 0 ]; then
    echo "⚠️  WARNING: No credentials found in credentials.txt"
    echo "   Please add your credentials in format: email:password"
    echo ""
    echo "   Example:"
    echo "   user@company.com:MyPassword123"
    echo ""
    read -p "Press Enter to continue anyway or Ctrl+C to exit..."
fi

echo "📋 Found $CRED_COUNT credentials to test"
echo ""

# Check config
if [ ! -f "site_config.json" ]; then
    echo "❌ site_config.json not found!"
    exit 1
fi

echo "⚙️  Configuration loaded"
echo ""

# Run validator
echo "🚀 Starting validation..."
echo "=============================================="
echo ""

python3 login_validator.py

echo ""
echo "=============================================="
echo "✅ Validation complete!"
echo ""
echo "📁 Check the results_*.txt file for detailed results"
echo "📝 Check validator.log for execution logs"
