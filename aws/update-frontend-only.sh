#!/bin/bash
# Fast frontend-only deployment
# Use when you've ONLY changed frontend code (no backend, no models)
# Timeline: 2-3 minutes

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
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
echo -e "${GREEN}   Frontend-Only Fast Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}⚡ Timeline: 2-3 minutes${NC}"
echo ""

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo -e "${YELLOW}Step 1: Building frontend image...${NC}"
cd ../frontend
# Use HTTPS domain, not ALB URL
API_URL="https://${DOMAIN_NAME:-rampart.arunrao.com}/api/v1"
echo "  API URL: $API_URL"
docker build --platform linux/amd64 \
  --build-arg NEXT_PUBLIC_API_URL="$API_URL" \
  --build-arg NEXT_PUBLIC_GITHUB_URL=https://github.com/arunrao/rampart-ai \
  -t rampart-frontend:latest .

echo ""
echo -e "${YELLOW}Step 2: Pushing to ECR...${NC}"
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
docker tag rampart-frontend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-frontend:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-frontend:latest

echo ""
echo -e "${YELLOW}Step 3: Restarting frontend containers on instances...${NC}"

# Get running instances
INSTANCE_IDS=$(aws ec2 describe-instances \
  --filters "Name=tag:aws:autoscaling:groupName,Values=${STACK_NAME}-asg" \
            "Name=instance-state-name,Values=running" \
  --query 'Reservations[*].Instances[*].InstanceId' \
  --output text \
  --region $AWS_REGION)

if [ -z "$INSTANCE_IDS" ]; then
    echo -e "${RED}❌ No running instances found${NC}"
    exit 1
fi

echo "  Found instances: $INSTANCE_IDS"

for INSTANCE_ID in $INSTANCE_IDS; do
    echo "  Restarting frontend on $INSTANCE_ID..."
    
    COMMAND_ID=$(aws ssm send-command \
      --instance-ids "$INSTANCE_ID" \
      --document-name "AWS-RunShellScript" \
      --parameters 'commands=[
        "cd /opt/rampart",
        "aws ecr get-login-password --region '$AWS_REGION' | docker login --username AWS --password-stdin '$AWS_ACCOUNT_ID'.dkr.ecr.'$AWS_REGION'.amazonaws.com",
        "docker-compose pull frontend",
        "docker-compose up -d --no-deps frontend",
        "echo \"✓ Frontend restarted\""
      ]' \
      --region $AWS_REGION \
      --output text \
      --query 'Command.CommandId')
    
    echo "    Command ID: $COMMAND_ID"
    
    # Wait a moment for command to execute
    sleep 3
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Frontend Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Timeline: ~2-3 minutes (vs 10-15 min full deployment)"
echo ""
echo "Verify at: https://rampart.arunrao.com"
echo ""
echo -e "${YELLOW}Note: This only works for frontend changes!${NC}"
echo "For backend/model changes, use ./update.sh or ./update-fast.sh"
echo ""
