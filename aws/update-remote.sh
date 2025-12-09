#!/bin/bash
# Remote-only update - rebuilds and restarts containers directly on EC2
# No local Docker required!
# Use for: dependency updates, config changes

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
echo -e "${GREEN}   Remote Update (No Local Docker!)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get AWS account
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "  Account ID: $AWS_ACCOUNT_ID"
echo "  Region: $AWS_REGION"
echo ""

# Step 1: Get EC2 instance IP
echo -e "${YELLOW}Step 1: Finding EC2 instance${NC}"

INSTANCE_IP=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=${STACK_NAME}-instance" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text \
  --region $AWS_REGION)

if [ -z "$INSTANCE_IP" ] || [ "$INSTANCE_IP" = "None" ]; then
    echo -e "${RED}  ❌ No running instance found${NC}"
    exit 1
fi

echo "  Instance IP: $INSTANCE_IP"
echo ""

# Find the key file
KEY_FILE=""
if [ -n "$KEY_PAIR_NAME" ]; then
    for loc in "$HOME/.ssh/${KEY_PAIR_NAME}.pem" "$HOME/.ssh/${KEY_PAIR_NAME}" "./${KEY_PAIR_NAME}.pem"; do
        if [ -f "$loc" ]; then
            KEY_FILE="$loc"
            break
        fi
    done
fi

if [ -z "$KEY_FILE" ]; then
    echo -e "${RED}  ❌ SSH key not found${NC}"
    echo ""
    echo "  Looking for: ${KEY_PAIR_NAME}.pem in ~/.ssh/ or current directory"
    echo ""
    echo "  Manual command:"
    echo -e "${BLUE}  ssh -i ~/.ssh/${KEY_PAIR_NAME}.pem ubuntu@$INSTANCE_IP${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 2: Connecting to EC2 and updating${NC}"
echo "  Using key: $KEY_FILE"
echo ""

# SSH and run remote commands
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i "$KEY_FILE" ubuntu@$INSTANCE_IP << 'EOF'
    set -e
    
    echo "📦 Pulling latest code changes..."
    
    # Check if rampart repo exists, if not we'll work with what's there
    if [ -d "/opt/rampart-repo" ]; then
        cd /opt/rampart-repo
        git pull origin main 2>/dev/null || echo "  (Using existing code)"
    fi
    
    cd /opt/rampart
    
    echo ""
    echo "🔄 Restarting containers with fresh pull..."
    
    # Login to ECR
    AWS_REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
    
    # Pull latest images from ECR (in case they were updated elsewhere)
    docker-compose pull
    
    # Restart with fresh containers
    docker-compose down
    docker-compose up -d
    
    echo ""
    echo "✅ Containers restarted!"
    echo ""
    docker-compose ps
    
    echo ""
    echo "🏥 Checking health..."
    sleep 5
    curl -s http://localhost:8000/api/v1/health || echo "  (Backend still starting...)"
EOF

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Remote Update Complete! 🚀${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Updated on: $INSTANCE_IP"
echo "Verify: curl https://${DOMAIN_NAME}/api/v1/health"
echo ""
