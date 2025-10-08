#!/bin/bash
# Delete the CloudFormation stack and all resources

RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

STACK_NAME="${STACK_NAME:-rampart-production}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo -e "${YELLOW}WARNING: This will delete all resources including:${NC}"
echo "  - EC2 instances"
echo "  - Load Balancer"
echo "  - RDS database (a final snapshot will be created)"
echo "  - All CloudFormation resources"
echo ""
echo "Stack: $STACK_NAME"
echo "Region: $AWS_REGION"
echo ""

read -p "Are you sure you want to proceed? (type 'yes' to confirm): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Deleting CloudFormation stack..."
aws cloudformation delete-stack \
  --stack-name $STACK_NAME \
  --region $AWS_REGION

echo "Stack deletion initiated. Monitoring progress..."
aws cloudformation wait stack-delete-complete \
  --stack-name $STACK_NAME \
  --region $AWS_REGION

echo ""
echo -e "${YELLOW}Optional: Delete ECR repositories?${NC}"
echo "This will delete all Docker images."
read -p "Delete ECR repositories? (type 'yes' to confirm): " DELETE_ECR

if [ "$DELETE_ECR" = "yes" ]; then
    echo "Deleting ECR repositories..."
    aws ecr delete-repository --repository-name rampart-backend --force --region $AWS_REGION 2>/dev/null || true
    aws ecr delete-repository --repository-name rampart-frontend --force --region $AWS_REGION 2>/dev/null || true
    echo "ECR repositories deleted."
fi

echo ""
echo "Cleanup complete!"
