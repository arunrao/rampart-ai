#!/bin/bash

# Fix CORS Issues - Quick Setup Script
# This script helps resolve CORS errors when using the web demo

echo "🛡️ RAMPART WEB DEMO - CORS FIX"
echo "=============================="
echo ""

# Check if we're in the demo directory
if [ ! -f "web_demo.html" ]; then
    echo "❌ Error: Please run this script from the demo directory"
    echo "   cd /path/to/project-rampart/demo"
    echo "   ./fix_cors.sh"
    exit 1
fi

# Check if backend is running
echo "🔍 Checking backend status..."
if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "✅ Backend is running"
else
    echo "❌ Backend is not running"
    echo "   Please start it with: docker-compose up -d"
    exit 1
fi

# Check if port 8081 is available
if lsof -i :8081 > /dev/null 2>&1; then
    echo "⚠️  Port 8081 is already in use"
    echo "   Trying to stop existing server..."
    pkill -f "serve_demo.py" 2>/dev/null || true
    sleep 2
fi

# Test CORS configuration
echo ""
echo "🧪 Testing CORS configuration..."
CORS_TEST=$(curl -s -X OPTIONS "http://localhost:8000/api/v1/security/analyze" \
    -H "Origin: http://localhost:8081" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: authorization,content-type" \
    -v 2>&1 | grep "access-control-allow-origin: http://localhost:8081")

if [ -n "$CORS_TEST" ]; then
    echo "✅ CORS is properly configured"
else
    echo "❌ CORS configuration issue detected"
    echo "   Backend may need to be restarted with updated CORS settings"
fi

# Start the demo server
echo ""
echo "🚀 Starting web demo server..."
echo "   URL: http://localhost:8081/web_demo.html"
echo "   Press Ctrl+C to stop"
echo ""

# Start server and open browser
python3 serve_demo.py
