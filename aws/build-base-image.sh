#!/bin/bash
# Build and push base image with ML models
# Run this ONLY when you change models or dependencies
# Typical frequency: Once per month or when adding new models

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Auto-source .env if it exists
if [ -f .env ]; then
    echo -e "${BLUE}📋 Loading configuration from .env...${NC}"
    set -a
    source .env
    set +a
    echo -e "${GREEN}✓ Configuration loaded${NC}"
    echo ""
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Building Base Image with ML Models${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "  Account ID: $AWS_ACCOUNT_ID"
echo "  Region: $AWS_REGION"
echo ""

echo -e "${YELLOW}This will take 10-15 minutes (downloads ~500MB of ML models)${NC}"
echo -e "${YELLOW}But you only need to do this when models change!${NC}"
echo ""

# Build base image
echo -e "${YELLOW}Step 1: Building base image with ML models...${NC}"
cd ../backend
docker build --platform linux/amd64 -f Dockerfile.base -t rampart-backend-base:latest .

# Tag for ECR
echo ""
echo -e "${YELLOW}Step 2: Tagging for ECR...${NC}"
docker tag rampart-backend-base:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-backend-base:latest

# Create ECR repository if it doesn't exist
echo ""
echo -e "${YELLOW}Step 3: Creating ECR repository (if needed)...${NC}"
if ! aws ecr describe-repositories --repository-names rampart-backend-base --region $AWS_REGION 2>/dev/null; then
    aws ecr create-repository --repository-name rampart-backend-base --region $AWS_REGION
    echo "  ✓ Created rampart-backend-base repository"
else
    echo "  ✓ Repository already exists"
fi

# Push to ECR
echo ""
echo -e "${YELLOW}Step 4: Pushing to ECR...${NC}"
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-backend-base:latest

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Base Image Ready!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Base image: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-backend-base:latest"
echo ""
echo "Now you can deploy code changes quickly with:"
echo -e "${BLUE}  ./update-fast.sh${NC}"
echo ""
