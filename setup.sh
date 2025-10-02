#!/bin/bash

# Project Rampart Setup Script
# This script helps you set up the development environment

set -e

echo "=========================================="
echo "Project Rampart - Setup Script"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Please install Python 3.9 or higher.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# Check Node.js version
echo "Checking Node.js version..."
if ! command -v node &> /dev/null; then
    echo -e "${RED}Node.js is not installed. Please install Node.js 18 or higher.${NC}"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
echo -e "${GREEN}✓ Node.js v$NODE_VERSION found${NC}"
echo ""

# Setup Backend
echo "=========================================="
echo "Setting up Backend (Python/FastAPI)"
echo "=========================================="

cd backend

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    
    # Generate random secret keys
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    
    # Update .env with generated keys
    sed -i.bak "s/your-secret-key-change-in-production/$SECRET_KEY/" .env
    sed -i.bak "s/your-jwt-secret-key/$JWT_SECRET_KEY/" .env
    rm .env.bak
    
    echo -e "${GREEN}✓ .env file created with random secret keys${NC}"
    echo -e "${YELLOW}⚠ Please add your LLM API keys to backend/.env${NC}"
else
    echo -e "${YELLOW}.env file already exists${NC}"
fi

cd ..

# Setup Frontend
echo ""
echo "=========================================="
echo "Setting up Frontend (Next.js)"
echo "=========================================="

cd frontend

# Install dependencies
echo "Installing Node.js dependencies..."
npm install
echo -e "${GREEN}✓ Node.js dependencies installed${NC}"

# Create .env.local file if it doesn't exist
if [ ! -f ".env.local" ]; then
    echo "Creating .env.local file..."
    cp .env.local.example .env.local
    echo -e "${GREEN}✓ .env.local file created${NC}"
else
    echo -e "${YELLOW}.env.local file already exists${NC}"
fi

cd ..

# Final instructions
echo ""
echo "=========================================="
echo "Setup Complete! 🎉"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Configure API keys (optional for testing):"
echo "   Edit backend/.env and add:"
echo "   - OPENAI_API_KEY=sk-..."
echo "   - ANTHROPIC_API_KEY=sk-ant-..."
echo ""
echo "2. Start the backend:"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   uvicorn api.main:app --reload"
echo ""
echo "3. In a new terminal, start the frontend:"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "4. Open your browser:"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Frontend: http://localhost:3000"
echo ""
echo "5. Try the examples:"
echo "   cd examples"
echo "   python api_client_example.py"
echo ""
echo "For more information, see QUICKSTART.md"
echo ""
