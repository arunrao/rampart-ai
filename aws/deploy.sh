#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Project Rampart AWS Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Auto-source .env if it exists
if [ -f .env ]; then
    echo -e "${BLUE}📋 Loading configuration from .env...${NC}"
    set -a  # Automatically export all variables
    source .env
    set +a
    echo -e "${GREEN}✓ Configuration loaded${NC}"
    echo ""
fi

# Check if setup hasn't been run
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  No .env file found${NC}"
    echo ""
    echo "Please run the setup wizard first:"
    echo -e "${BLUE}  ./setup.sh${NC}"
    echo ""
    echo "This will help you configure all required parameters."
    echo ""
    exit 1
fi

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    echo "Install it from: https://aws.amazon.com/cli/"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Install it from: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured${NC}"
    echo "Run: aws configure"
    exit 1
fi

# Verify required variables are set
MISSING_VARS=0
for var in STACK_NAME AWS_REGION GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET DB_PASSWORD KEY_PAIR_NAME; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}Error: $var is not set${NC}"
        MISSING_VARS=1
    fi
done

if [ $MISSING_VARS -eq 1 ]; then
    echo ""
    echo "Please ensure you've run:"
    echo -e "${BLUE}  source .env${NC}"
    exit 1
fi

# Configuration
echo -e "${YELLOW}Configuration:${NC}"
echo "  Stack Name: $STACK_NAME"
echo "  AWS Region: $AWS_REGION"
echo "  Key Pair: $KEY_PAIR_NAME"
echo "  Instance Type: ${INSTANCE_TYPE:-t3.medium}"
[ -n "$DOMAIN_NAME" ] && echo "  Domain: $DOMAIN_NAME"
echo ""

echo ""
echo -e "${YELLOW}Step 1: Getting AWS Account ID${NC}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "  Account ID: $AWS_ACCOUNT_ID"

echo ""
echo -e "${YELLOW}Step 2: Building Docker Images${NC}"

# Build backend
echo "  Building backend image for AMD64..."
cd ../backend
docker build --platform linux/amd64 -t rampart-backend:latest .

# Build frontend
echo "  Building frontend image for AMD64..."
cd ../frontend
# Build with the actual domain URL
docker build --platform linux/amd64 \
  --build-arg NEXT_PUBLIC_API_URL=https://${DOMAIN_NAME}/api/v1 \
  --build-arg NEXT_PUBLIC_GITHUB_URL=https://github.com/arunrao/rampart-ai \
  -t rampart-frontend:latest .

cd ../aws

echo ""
echo -e "${YELLOW}Step 3: Creating ECR Repositories (if they don't exist)${NC}"

# Check if repositories exist, create if they don't
if ! aws ecr describe-repositories --repository-names rampart-backend --region $AWS_REGION 2>/dev/null; then
    aws ecr create-repository --repository-name rampart-backend --region $AWS_REGION
    echo "  ✓ Created rampart-backend repository"
else
    echo "  ✓ rampart-backend repository already exists"
fi

if ! aws ecr describe-repositories --repository-names rampart-frontend --region $AWS_REGION 2>/dev/null; then
    aws ecr create-repository --repository-name rampart-frontend --region $AWS_REGION
    echo "  ✓ Created rampart-frontend repository"
else
    echo "  ✓ rampart-frontend repository already exists"
fi

echo ""
echo -e "${YELLOW}Step 4: Pushing Docker Images to ECR${NC}"

# Login to ECR
echo "  Logging in to ECR..."
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
echo -e "${YELLOW}Step 5: Deploying CloudFormation Stack${NC}"

# Create parameters file
cat > /tmp/cfn-parameters.json << EOF
[
  {
    "ParameterKey": "Environment",
    "ParameterValue": "production"
  },
  {
    "ParameterKey": "GoogleClientId",
    "ParameterValue": "$GOOGLE_CLIENT_ID"
  },
  {
    "ParameterKey": "GoogleClientSecret",
    "ParameterValue": "$GOOGLE_CLIENT_SECRET"
  },
  {
    "ParameterKey": "DBPassword",
    "ParameterValue": "$DB_PASSWORD"
  },
  {
    "ParameterKey": "KeyPairName",
    "ParameterValue": "$KEY_PAIR_NAME"
  },
  {
    "ParameterKey": "DomainName",
    "ParameterValue": "$DOMAIN_NAME"
  }
]
EOF

# Deploy stack
echo "  Creating/Updating stack... (this may take 10-15 minutes)"
aws cloudformation deploy \
  --template-file cloudformation/infrastructure.yaml \
  --stack-name $STACK_NAME \
  --parameter-overrides file:///tmp/cfn-parameters.json \
  --capabilities CAPABILITY_IAM \
  --region $AWS_REGION

# Clean up parameters file
rm /tmp/cfn-parameters.json

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get outputs
echo -e "${YELLOW}Application URLs:${NC}"
FRONTEND_URL=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`FrontendURL`].OutputValue' --output text)
BACKEND_URL=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`BackendAPIURL`].OutputValue' --output text)

echo "  Frontend: $FRONTEND_URL"
echo "  Backend API: $BACKEND_URL"
echo "  API Docs: $BACKEND_URL/docs"
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Update Google OAuth redirect URIs to include:"
echo "     - $BACKEND_URL/auth/google/callback"
echo "  2. Wait 5-10 minutes for the application to fully start"
echo "  3. Visit $FRONTEND_URL to access your application"
echo ""

echo -e "${YELLOW}Useful Commands:${NC}"
echo "  View logs: ./logs.sh"
echo "  Update deployment: ./deploy.sh"
echo "  Delete stack: ./cleanup.sh"
echo ""

echo -e "${GREEN}Deployment successful! 🚀${NC}"
