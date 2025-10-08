#!/bin/bash
# Setup script - validates prerequisites and creates .env file

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Project Rampart - Setup Wizard${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"
echo ""

ERRORS=0

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}✗ AWS CLI not installed${NC}"
    echo "  Install from: https://aws.amazon.com/cli/"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✓ AWS CLI installed${NC}"
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not installed${NC}"
    echo "  Install from: https://docs.docker.com/get-docker/"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✓ Docker installed${NC}"
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}✗ AWS credentials not configured${NC}"
    echo ""
    echo "  You need AWS access keys to deploy."
    echo "  See: AWS_CREDENTIALS_GUIDE.md for step-by-step instructions"
    echo ""
    echo "  Quick steps:"
    echo "  1. Go to https://console.aws.amazon.com/"
    echo "  2. Navigate to IAM → Users → Create user"
    echo "  3. Create access keys for the user"
    echo "  4. Run: aws configure"
    echo ""
    ERRORS=$((ERRORS + 1))
else
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    AWS_USER=$(aws sts get-caller-identity --query Arn --output text | cut -d'/' -f2)
    echo -e "${GREEN}✓ AWS credentials configured${NC}"
    echo "  Account: $AWS_ACCOUNT_ID"
    echo "  User: $AWS_USER"
fi

echo ""

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}Please fix the errors above before continuing${NC}"
    exit 1
fi

echo -e "${GREEN}All prerequisites met!${NC}"
echo ""

# Check if .env already exists
if [ -f .env ]; then
    echo -e "${YELLOW}.env file already exists${NC}"
    read -p "Do you want to overwrite it? (y/N): " OVERWRITE
    if [ "$OVERWRITE" != "y" ] && [ "$OVERWRITE" != "Y" ]; then
        echo "Using existing .env file"
        exit 0
    fi
fi

echo -e "${YELLOW}Let's configure your deployment...${NC}"
echo ""

# Stack configuration
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Stack Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

read -p "Stack name [rampart-production]: " STACK_NAME
STACK_NAME=${STACK_NAME:-rampart-production}

read -p "AWS Region [us-east-1]: " AWS_REGION
AWS_REGION=${AWS_REGION:-us-east-1}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. Google OAuth Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Get your credentials from:"
echo "https://console.cloud.google.com/apis/credentials"
echo ""

read -p "Google OAuth Client ID: " GOOGLE_CLIENT_ID
while [ -z "$GOOGLE_CLIENT_ID" ]; do
    echo -e "${RED}Client ID is required${NC}"
    read -p "Google OAuth Client ID: " GOOGLE_CLIENT_ID
done

read -sp "Google OAuth Client Secret: " GOOGLE_CLIENT_SECRET
echo ""
while [ -z "$GOOGLE_CLIENT_SECRET" ]; do
    echo -e "${RED}Client Secret is required${NC}"
    read -sp "Google OAuth Client Secret: " GOOGLE_CLIENT_SECRET
    echo ""
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Database Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

read -sp "RDS Database Password (min 8 characters): " DB_PASSWORD
echo ""
while [ ${#DB_PASSWORD} -lt 8 ]; do
    echo -e "${RED}Password must be at least 8 characters${NC}"
    read -sp "RDS Database Password (min 8 characters): " DB_PASSWORD
    echo ""
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. EC2 Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# List available key pairs
echo "Available EC2 Key Pairs in $AWS_REGION:"
aws ec2 describe-key-pairs --region $AWS_REGION --query 'KeyPairs[*].KeyName' --output text | tr '\t' '\n' | nl
echo ""

read -p "EC2 Key Pair Name: " KEY_PAIR_NAME
while [ -z "$KEY_PAIR_NAME" ]; do
    echo -e "${RED}Key Pair Name is required (for SSH access)${NC}"
    read -p "EC2 Key Pair Name: " KEY_PAIR_NAME
done

# Verify key pair exists
if ! aws ec2 describe-key-pairs --key-names "$KEY_PAIR_NAME" --region $AWS_REGION &> /dev/null; then
    echo -e "${RED}Key pair '$KEY_PAIR_NAME' not found in $AWS_REGION${NC}"
    echo "Create one at: https://console.aws.amazon.com/ec2/home?region=$AWS_REGION#KeyPairs:"
    exit 1
fi

echo ""
read -p "Instance Type [t3.medium] (t3.small/t3.medium/t3.large): " INSTANCE_TYPE
INSTANCE_TYPE=${INSTANCE_TYPE:-t3.medium}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. Optional: Custom Domain"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "Domain Name (press Enter to skip): " DOMAIN_NAME

# Create .env file
echo ""
echo -e "${YELLOW}Creating .env file...${NC}"

cat > .env << EOF
# Project Rampart AWS Deployment Configuration
# Generated on $(date)

# Stack Configuration
export STACK_NAME="$STACK_NAME"
export AWS_REGION="$AWS_REGION"

# Google OAuth
export GOOGLE_CLIENT_ID="$GOOGLE_CLIENT_ID"
export GOOGLE_CLIENT_SECRET="$GOOGLE_CLIENT_SECRET"

# Database
export DB_PASSWORD="$DB_PASSWORD"

# EC2
export KEY_PAIR_NAME="$KEY_PAIR_NAME"
export INSTANCE_TYPE="$INSTANCE_TYPE"

# Domain (optional)
export DOMAIN_NAME="$DOMAIN_NAME"
EOF

chmod 600 .env  # Secure the file

echo -e "${GREEN}✓ Configuration saved to .env${NC}"
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}Configuration Summary${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Stack Name:     $STACK_NAME"
echo "AWS Region:     $AWS_REGION"
echo "AWS Account:    $AWS_ACCOUNT_ID"
echo "Instance Type:  $INSTANCE_TYPE"
echo "Key Pair:       $KEY_PAIR_NAME"
echo "Domain:         ${DOMAIN_NAME:-None}"
echo ""

# Estimate cost
case $INSTANCE_TYPE in
    t3.small)
        EC2_COST="~\$15"
        TOTAL_COST="~\$45-50"
        ;;
    t3.medium)
        EC2_COST="~\$30"
        TOTAL_COST="~\$60-70"
        ;;
    t3.large)
        EC2_COST="~\$60"
        TOTAL_COST="~\$90-100"
        ;;
esac

echo "Estimated Monthly Cost:"
echo "  EC2 ($INSTANCE_TYPE): $EC2_COST/month"
echo "  RDS (db.t3.micro):    ~\$15/month"
echo "  Load Balancer:        ~\$16/month"
echo "  Other:                ~\$5/month"
echo "  ──────────────────────────────"
echo "  Total:                $TOTAL_COST/month"
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Review the configuration above"
echo "  2. Run: source .env"
echo "  3. Run: ./deploy.sh"
echo ""
echo -e "${GREEN}Setup complete! 🚀${NC}"
