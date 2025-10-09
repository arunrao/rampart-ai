#!/bin/bash
# Monitor instance refresh progress

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

STACK_NAME="${STACK_NAME:-rampart-production}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Get Auto Scaling Group name
ASG_NAME=$(aws autoscaling describe-auto-scaling-groups \
  --query "AutoScalingGroups[?contains(AutoScalingGroupName, '${STACK_NAME}')].AutoScalingGroupName" \
  --output text \
  --region $AWS_REGION)

if [ -z "$ASG_NAME" ]; then
    echo -e "${RED}❌ Auto Scaling Group not found${NC}"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Monitoring Deployment Progress${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Auto Scaling Group: $ASG_NAME"
echo ""

# Monitor the refresh
while true; do
    REFRESH_INFO=$(aws autoscaling describe-instance-refreshes \
      --auto-scaling-group-name "$ASG_NAME" \
      --region $AWS_REGION \
      --query 'InstanceRefreshes[0]' \
      --output json)
    
    STATUS=$(echo "$REFRESH_INFO" | jq -r '.Status')
    PERCENTAGE=$(echo "$REFRESH_INFO" | jq -r '.PercentageComplete')
    START_TIME=$(echo "$REFRESH_INFO" | jq -r '.StartTime')
    
    clear
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}   Deployment Progress${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo "Status: $STATUS"
    echo "Progress: ${PERCENTAGE}%"
    echo "Started: $START_TIME"
    echo ""
    
    # Show progress bar
    FILLED=$((PERCENTAGE / 2))
    EMPTY=$((50 - FILLED))
    printf "["
    for i in $(seq 1 $FILLED); do printf "="; done
    for i in $(seq 1 $EMPTY); do printf " "; done
    printf "] ${PERCENTAGE}%%\n"
    echo ""
    
    # Show detailed status
    echo "Instances to update:"
    echo "$REFRESH_INFO" | jq -r '.InstancesToUpdate' | sed 's/^/  /'
    echo ""
    
    if [ "$STATUS" = "Successful" ]; then
        echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
        echo ""
        echo "Testing endpoints..."
        echo ""
        
        # Get ALB DNS
        ALB_URL=$(aws cloudformation describe-stacks \
          --stack-name $STACK_NAME \
          --region $AWS_REGION \
          --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerURL`].OutputValue' \
          --output text)
        
        echo "Backend Health:"
        curl -s "${ALB_URL}/api/v1/health" | jq '.' || echo "  Failed"
        echo ""
        echo "Frontend:"
        curl -s "$ALB_URL" -I | head -3
        echo ""
        break
    elif [ "$STATUS" = "Failed" ] || [ "$STATUS" = "Cancelled" ]; then
        echo -e "${RED}❌ Deployment $STATUS${NC}"
        echo ""
        echo "Reason:"
        echo "$REFRESH_INFO" | jq -r '.StatusReason' | sed 's/^/  /'
        echo ""
        break
    elif [ "$STATUS" = "InProgress" ] || [ "$STATUS" = "Pending" ]; then
        echo -e "${YELLOW}⏳ Deployment in progress...${NC}"
        echo ""
        echo "Refresh will continue in the background."
        echo "Press Ctrl+C to stop monitoring (deployment will continue)"
        echo ""
        sleep 10
    else
        echo "Unknown status: $STATUS"
        sleep 10
    fi
done

