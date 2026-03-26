#!/bin/bash
# Update the application with new code

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Auto-source .env if it exists
if [ -f .env ]; then
    echo -e "${BLUE}📋 Loading configuration from .env...${NC}"
    set -a  # Automatically export all variables
    source .env
    set +a
    echo -e "${GREEN}✓ Configuration loaded${NC}"
    echo ""
fi

STACK_NAME="${STACK_NAME:-rampart-production}"
AWS_REGION="${AWS_REGION:-us-west-2}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Updating Project Rampart${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${YELLOW}Step 1: Getting AWS Account ID${NC}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "  Account ID: $AWS_ACCOUNT_ID"

echo ""
echo -e "${YELLOW}Step 2: Building New Docker Images${NC}"

# Build backend
echo "  Building backend image..."
cd ../backend
docker build --platform linux/amd64 -t rampart-backend:latest .

# Build frontend
echo "  Building frontend image..."
cd ../frontend
# Use HTTPS domain, not ALB URL
API_URL="https://${DOMAIN_NAME:-rampart.arunrao.com}/api/v1"
docker build --platform linux/amd64 \
  --build-arg NEXT_PUBLIC_API_URL="$API_URL" \
  --build-arg NEXT_PUBLIC_GITHUB_URL=https://github.com/arunrao/rampart-ai \
  -t rampart-frontend:latest .

cd ../aws

echo ""
echo -e "${YELLOW}Step 3: Pushing Docker Images to ECR${NC}"

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag and push backend
echo "  Pushing backend image..."
docker tag rampart-backend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-backend:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-backend:latest

# Tag and push frontend
echo "  Pushing frontend image..."
docker tag rampart-frontend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-frontend:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-frontend:latest

echo ""
echo -e "${YELLOW}Step 4: Triggering Instance Refresh (Zero-Downtime Deployment)${NC}"

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
    echo "  Waiting for cancellation to complete..."
    for i in $(seq 1 12); do
      sleep 5
      STATUS=$(aws autoscaling describe-instance-refreshes \
        --auto-scaling-group-name "$ASG_NAME" \
        --region $AWS_REGION \
        --query 'InstanceRefreshes[0].Status' \
        --output text)
      echo "    Status: $STATUS"
      if [ "$STATUS" = "Cancelled" ] || [ "$STATUS" = "Failed" ]; then
        echo "  ✓ Previous refresh cancelled"
        break
      fi
    done
fi

# Start instance refresh with proper configuration
echo "  Starting instance refresh..."
REFRESH_ID=$(aws autoscaling start-instance-refresh \
  --auto-scaling-group-name "$ASG_NAME" \
  --preferences '{
    "MinHealthyPercentage": 100,
    "MaxHealthyPercentage": 200,
    "InstanceWarmup": 300,
    "CheckpointPercentages": [100],
    "CheckpointDelay": 60,
    "SkipMatching": false
  }' \
  --region $AWS_REGION \
  --query 'InstanceRefreshId' \
  --output text)

echo "  ✅ Instance Refresh Started: $REFRESH_ID"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Deployment Started!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Instance Refresh ID: $REFRESH_ID"
echo ""
echo "The deployment will:"
echo "  • Maintain 50% healthy instances during rollout"
echo "  • Wait 5 minutes for ML models to load on new instances"
echo "  • Replace instances one at a time"
echo "  • Total time: ~10-15 minutes"
echo ""
echo "Monitor progress with:"
echo "  aws autoscaling describe-instance-refreshes \\"
echo "    --auto-scaling-group-name $ASG_NAME \\"
echo "    --region $AWS_REGION"
echo ""
echo -e "${YELLOW}⏳ Deployment in progress...${NC}"
