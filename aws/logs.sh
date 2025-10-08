#!/bin/bash
# View application logs from EC2 instances

STACK_NAME="${STACK_NAME:-rampart-production}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "Fetching instance IDs..."
INSTANCE_IDS=$(aws ec2 describe-instances \
  --filters "Name=tag:aws:autoscaling:groupName,Values=${STACK_NAME}-asg" \
            "Name=instance-state-name,Values=running" \
  --query 'Reservations[*].Instances[*].InstanceId' \
  --output text \
  --region $AWS_REGION)

if [ -z "$INSTANCE_IDS" ]; then
    echo "No running instances found"
    exit 1
fi

echo "Found instances: $INSTANCE_IDS"
echo ""

for INSTANCE_ID in $INSTANCE_IDS; do
    echo "========================================="
    echo "Logs from instance: $INSTANCE_ID"
    echo "========================================="
    
    # Get logs via SSM
    aws ssm send-command \
      --instance-ids "$INSTANCE_ID" \
      --document-name "AWS-RunShellScript" \
      --parameters 'commands=["cd /opt/rampart && docker-compose logs --tail=50"]' \
      --region $AWS_REGION \
      --output text
    
    echo ""
done

echo "To view real-time logs, SSH into an instance:"
echo "  ssh -i your-key.pem ubuntu@<instance-public-ip>"
echo "  cd /opt/rampart"
echo "  docker-compose logs -f"
