#!/bin/bash
# Quick update - builds, pushes to ECR, and restarts containers via SSH
# Much faster than instance refresh (~3 min vs ~15 min)
# Use for: dependency updates, minor code changes

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
echo -e "${GREEN}   Quick Update (SSH + Restart)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Parse arguments
BUILD_BACKEND=true
BUILD_FRONTEND=true

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --backend-only) BUILD_FRONTEND=false ;;
        --frontend-only) BUILD_BACKEND=false ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --backend-only   Only update backend"
            echo "  --frontend-only  Only update frontend"
            echo "  -h, --help       Show this help"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# Get AWS account
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "  Account ID: $AWS_ACCOUNT_ID"
echo "  Region: $AWS_REGION"
echo ""

# Step 1: Build images
echo -e "${YELLOW}Step 1: Building Docker images${NC}"

if [ "$BUILD_BACKEND" = true ]; then
    echo "  Building backend..."
    cd ../backend
    docker build --platform linux/amd64 -t rampart-backend:latest . 2>&1 | tail -5
    cd ../aws
fi

if [ "$BUILD_FRONTEND" = true ]; then
    echo "  Building frontend..."
    cd ../frontend
    API_URL="https://${DOMAIN_NAME:-rampart.arunrao.com}/api/v1"
    docker build --platform linux/amd64 \
      --build-arg NEXT_PUBLIC_API_URL="$API_URL" \
      --build-arg NEXT_PUBLIC_GITHUB_URL=https://github.com/arunrao/rampart-ai \
      -t rampart-frontend:latest . 2>&1 | tail -5
    cd ../aws
fi

echo -e "${GREEN}  ✓ Images built${NC}"
echo ""

# Step 2: Push to ECR
echo -e "${YELLOW}Step 2: Pushing to ECR${NC}"

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com 2>/dev/null

if [ "$BUILD_BACKEND" = true ]; then
    echo "  Pushing backend..."
    docker tag rampart-backend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-backend:latest
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-backend:latest 2>&1 | tail -3
fi

if [ "$BUILD_FRONTEND" = true ]; then
    echo "  Pushing frontend..."
    docker tag rampart-frontend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-frontend:latest
    docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-frontend:latest 2>&1 | tail -3
fi

echo -e "${GREEN}  ✓ Images pushed${NC}"
echo ""

# Step 3: Get EC2 instance IP
echo -e "${YELLOW}Step 3: Finding EC2 instance${NC}"

INSTANCE_IP=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=${STACK_NAME}-instance" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region $AWS_REGION)

if [ -z "$INSTANCE_IP" ] || [ "$INSTANCE_IP" = "None" ]; then
    echo -e "${RED}  ❌ No running instance found${NC}"
    echo "  Falling back to instance refresh..."
    ./update.sh
    exit 0
fi

echo "  Instance IP: $INSTANCE_IP"
echo ""

# Step 4: SSH and restart containers
echo -e "${YELLOW}Step 4: Restarting containers via SSH${NC}"

# Determine which services to restart
if [ "$BUILD_BACKEND" = true ] && [ "$BUILD_FRONTEND" = true ]; then
    SERVICES=""
elif [ "$BUILD_BACKEND" = true ]; then
    SERVICES="backend"
else
    SERVICES="frontend"
fi

# Find the key file
KEY_FILE=""
if [ -n "$KEY_PAIR_NAME" ]; then
    # Check common locations
    for loc in "$HOME/.ssh/${KEY_PAIR_NAME}.pem" "$HOME/.ssh/${KEY_PAIR_NAME}" "./${KEY_PAIR_NAME}.pem"; do
        if [ -f "$loc" ]; then
            KEY_FILE="$loc"
            break
        fi
    done
fi

if [ -z "$KEY_FILE" ]; then
    echo -e "${YELLOW}  ⚠️  SSH key not found automatically${NC}"
    echo ""
    echo "  Run these commands manually:"
    echo -e "${BLUE}  ssh -i ~/.ssh/${KEY_PAIR_NAME}.pem ubuntu@$INSTANCE_IP${NC}"
    echo -e "${BLUE}  cd /opt/rampart && docker-compose pull $SERVICES && docker-compose up -d $SERVICES${NC}"
    echo ""
    exit 0
fi

echo "  Using key: $KEY_FILE"
echo "  Connecting to $INSTANCE_IP..."

# SSH commands
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i "$KEY_FILE" ubuntu@$INSTANCE_IP << EOF
    set -e
    cd /opt/rampart
    
    # Login to ECR
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
    
    # Pull new images
    echo "Pulling new images..."
    docker-compose pull $SERVICES
    
    # Restart services
    echo "Restarting services..."
    docker-compose up -d $SERVICES
    
    echo "Done!"
    docker-compose ps
EOF

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Quick Update Complete! 🚀${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Services updated and restarted on $INSTANCE_IP"
echo ""
echo "Verify with:"
echo "  curl https://${DOMAIN_NAME}/api/v1/health"
echo ""
