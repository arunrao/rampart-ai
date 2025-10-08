#!/bin/bash
# Update the application with new code

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

STACK_NAME="${STACK_NAME:-rampart-production}"
AWS_REGION="${AWS_REGION:-us-east-1}"

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
docker build -t rampart-backend:latest .

# Build frontend
echo "  Building frontend image..."
cd ../frontend
ALB_DNS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerURL`].OutputValue' --output text | sed 's|http://||')
docker build --build-arg NEXT_PUBLIC_API_URL=http://$ALB_DNS/api/v1 -t rampart-frontend:latest .

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
echo -e "${YELLOW}Step 4: Restarting Application on EC2 Instances${NC}"

# Get instance IDs
INSTANCE_IDS=$(aws ec2 describe-instances \
  --filters "Name=tag:aws:autoscaling:groupName,Values=${STACK_NAME}-asg" \
            "Name=instance-state-name,Values=running" \
  --query 'Reservations[*].Instances[*].InstanceId' \
  --output text \
  --region $AWS_REGION)

if [ -z "$INSTANCE_IDS" ]; then
    echo "  No running instances found"
    exit 1
fi

echo "  Updating instances: $INSTANCE_IDS"

for INSTANCE_ID in $INSTANCE_IDS; do
    echo "  Restarting containers on $INSTANCE_ID..."
    
    COMMAND_ID=$(aws ssm send-command \
      --instance-ids "$INSTANCE_ID" \
      --document-name "AWS-RunShellScript" \
      --parameters 'commands=["cd /opt/rampart","aws ecr get-login-password --region '${AWS_REGION}' | docker login --username AWS --password-stdin '${AWS_ACCOUNT_ID}'.dkr.ecr.'${AWS_REGION}'.amazonaws.com","docker-compose pull","docker-compose up -d"]' \
      --region $AWS_REGION \
      --query 'Command.CommandId' \
      --output text)
    
    echo "  Command ID: $COMMAND_ID"
done

echo ""
echo -e "${GREEN}Update complete! 🚀${NC}"
echo "Containers are restarting with the new images."
echo "Wait 2-3 minutes for the application to be fully available."
