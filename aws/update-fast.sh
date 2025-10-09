#!/bin/bash
# Fast code-only deployment using base image
# Uses pre-built base image with ML models
# Typical deployment time: 3-5 minutes (vs 10-15 minutes)

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

STACK_NAME="${STACK_NAME:-rampart-production}"
AWS_REGION="${AWS_REGION:-us-west-2}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Fast Code-Only Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "  Account ID: $AWS_ACCOUNT_ID"
echo "  Region: $AWS_REGION"
echo ""

echo -e "${YELLOW}Step 1: Building application images (fast!)${NC}"

# Build backend using base image
echo "  Building backend..."
cd ../backend
docker build --platform linux/amd64 \
  -f Dockerfile.app \
  --build-arg BASE_IMAGE=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-backend-base:latest \
  -t rampart-backend:latest .

# Build frontend
echo "  Building frontend..."
cd ../frontend
# Use HTTPS domain, not ALB URL
API_URL="https://${DOMAIN_NAME:-rampart.arunrao.com}/api/v1"
docker build --platform linux/amd64 \
  --build-arg NEXT_PUBLIC_API_URL="$API_URL" \
  --build-arg NEXT_PUBLIC_GITHUB_URL=https://github.com/arunrao/rampart-ai \
  -t rampart-frontend:latest .

cd ../aws

echo ""
echo -e "${YELLOW}Step 2: Pushing images to ECR${NC}"

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Push backend
echo "  Pushing backend..."
docker tag rampart-backend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-backend:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-backend:latest

# Push frontend
echo "  Pushing frontend..."
docker tag rampart-frontend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-frontend:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-frontend:latest

echo ""
echo -e "${YELLOW}Step 3: Triggering Instance Refresh${NC}"

# Get Auto Scaling Group name
ASG_NAME=$(aws autoscaling describe-auto-scaling-groups \
  --query "AutoScalingGroups[?contains(AutoScalingGroupName, '${STACK_NAME}')].AutoScalingGroupName" \
  --output text \
  --region $AWS_REGION)

if [ -z "$ASG_NAME" ]; then
    echo "  ❌ Auto Scaling Group not found"
    exit 1
fi

echo "  Auto Scaling Group: $ASG_NAME"

# Check if there's already an instance refresh in progress
EXISTING_REFRESH=$(aws autoscaling describe-instance-refreshes \
  --auto-scaling-group-name "$ASG_NAME" \
  --region $AWS_REGION \
  --query 'InstanceRefreshes[?Status==`InProgress`].InstanceRefreshId' \
  --output text)

if [ -n "$EXISTING_REFRESH" ]; then
    echo "  ⚠️  Instance refresh already in progress: $EXISTING_REFRESH"
    echo "  Cancelling existing refresh..."
    aws autoscaling cancel-instance-refresh \
      --auto-scaling-group-name "$ASG_NAME" \
      --region $AWS_REGION
    sleep 5
fi

# Start instance refresh
echo "  Starting instance refresh..."
REFRESH_ID=$(aws autoscaling start-instance-refresh \
  --auto-scaling-group-name "$ASG_NAME" \
  --preferences '{
    "MinHealthyPercentage": 50,
    "InstanceWarmup": 180,
    "CheckpointPercentages": [50, 100],
    "CheckpointDelay": 30,
    "SkipMatching": false
  }' \
  --region $AWS_REGION \
  --query 'InstanceRefreshId' \
  --output text)

echo "  ✅ Instance Refresh Started: $REFRESH_ID"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Fast Deployment Started!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Instance Refresh ID: $REFRESH_ID"
echo ""
echo "Expected deployment time: ~3-5 minutes"
echo "  (vs 10-15 min with full model rebuild)"
echo ""
echo "The deployment will:"
echo "  • Use pre-loaded ML models from base image"
echo "  • Wait only 3 minutes for warmup (vs 5 min)"
echo "  • Replace instances with new code"
echo ""
echo "Monitor progress with:"
echo "  ./monitor-deployment.sh"
echo ""
echo -e "${YELLOW}⏳ Deployment in progress...${NC}"
