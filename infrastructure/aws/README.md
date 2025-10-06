# AWS Infrastructure Deployment Guide

This directory contains Terraform configuration for deploying Project Rampart to AWS with auto-scaling capabilities.

## Architecture

- **Compute**: ECS Fargate (serverless containers)
- **Database**: RDS Aurora PostgreSQL (Multi-AZ)
- **Cache**: ElastiCache Redis (cluster mode)
- **Load Balancer**: Application Load Balancer
- **Secrets**: AWS Secrets Manager
- **Logs**: CloudWatch Logs
- **Container Registry**: ECR

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **Terraform** >= 1.0 installed
4. **Docker** installed for building images

## Quick Start

### 1. Configure AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and default region
```

### 2. Initialize Terraform

```bash
cd infrastructure/aws
terraform init
```

### 3. Review and Customize Variables

Edit `terraform.tfvars` (create if it doesn't exist):

```hcl
aws_region         = "us-east-1"
environment        = "production"
app_name           = "rampart"
db_instance_class  = "db.r6g.large"
redis_node_type    = "cache.r6g.large"
ecs_desired_count  = 2
ecs_min_capacity   = 2
ecs_max_capacity   = 20
```

### 4. Plan Deployment

```bash
terraform plan -out=tfplan
```

Review the planned changes carefully.

### 5. Apply Infrastructure

```bash
terraform apply tfplan
```

This will create:
- VPC with public/private subnets
- RDS Aurora PostgreSQL cluster
- ElastiCache Redis cluster
- ECS cluster and task definitions
- Application Load Balancer
- Auto-scaling policies
- Security groups and IAM roles

**Estimated time**: 15-20 minutes

### 6. Build and Push Docker Image

```bash
# Get ECR repository URL from Terraform output
ECR_URL=$(terraform output -raw ecr_repository_url)

# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $ECR_URL

# Build and tag image
cd ../../backend
docker build -t rampart-backend .
docker tag rampart-backend:latest $ECR_URL:latest

# Push to ECR
docker push $ECR_URL:latest
```

### 7. Update ECS Service

```bash
# Force new deployment with updated image
aws ecs update-service \
  --cluster rampart-cluster \
  --service rampart-backend-service \
  --force-new-deployment
```

### 8. Get Application URL

```bash
terraform output alb_dns_name
# Output: rampart-alb-1234567890.us-east-1.elb.amazonaws.com
```

Access your API at: `http://<alb-dns-name>/health`

## Configuration

### Environment Variables

The ECS task automatically receives these environment variables:

- `ENVIRONMENT`: production
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `SECRET_KEY`: From Secrets Manager
- `JWT_SECRET_KEY`: From Secrets Manager
- `KEY_ENCRYPTION_SECRET`: From Secrets Manager

### Secrets Management

Retrieve secrets for local development:

```bash
# Database password
aws secretsmanager get-secret-value \
  --secret-id rampart/db-password \
  --query SecretString \
  --output text

# Or use Terraform output
terraform output -raw database_password
```

### Scaling Configuration

**Auto-scaling triggers**:
- CPU utilization > 70% → scale out
- Memory utilization > 80% → scale out
- CPU/Memory < threshold for 5 minutes → scale in

**Manual scaling**:
```bash
aws ecs update-service \
  --cluster rampart-cluster \
  --service rampart-backend-service \
  --desired-count 5
```

## Monitoring

### CloudWatch Logs

```bash
# View logs
aws logs tail /ecs/rampart-backend --follow

# Filter for errors
aws logs filter-log-events \
  --log-group-name /ecs/rampart-backend \
  --filter-pattern "ERROR"
```

### CloudWatch Metrics

Key metrics to monitor:
- `ECSServiceAverageCPUUtilization`
- `ECSServiceAverageMemoryUtilization`
- `TargetResponseTime`
- `HealthyHostCount`
- `UnHealthyHostCount`

### Alarms

Create CloudWatch alarms:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name rampart-high-cpu \
  --alarm-description "Alert when CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

## Database Management

### Connect to RDS

```bash
# Get endpoint
RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
DB_PASSWORD=$(terraform output -raw database_password)

# Connect via psql
psql -h $RDS_ENDPOINT -U rampart_admin -d rampart
```

### Run Migrations

```bash
# From local machine (requires VPN or bastion host)
export DATABASE_URL="postgresql://rampart_admin:$DB_PASSWORD@$RDS_ENDPOINT:5432/rampart"
cd backend
alembic upgrade head
```

### Backups

- **Automated backups**: Daily at 3:00 AM UTC (7-day retention)
- **Manual snapshot**: 
  ```bash
  aws rds create-db-cluster-snapshot \
    --db-cluster-identifier rampart-cluster \
    --db-cluster-snapshot-identifier rampart-manual-snapshot-$(date +%Y%m%d)
  ```

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/deploy-aws.yml`:

```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Login to ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1
      
      - name: Build and push image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: rampart-backend
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG ./backend
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
      
      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster rampart-cluster \
            --service rampart-backend-service \
            --force-new-deployment
```

## Cost Optimization

### Development Environment

For lower costs in dev/staging:

```hcl
# terraform.tfvars
db_instance_class  = "db.t4g.medium"  # $50/month vs $300/month
redis_node_type    = "cache.t4g.small"  # $15/month vs $150/month
ecs_desired_count  = 1
ecs_max_capacity   = 5
```

### Production Optimizations

1. **Use Savings Plans**: 30-50% discount on compute
2. **Reserved Instances**: For RDS and ElastiCache
3. **Auto-scaling**: Scale down during off-hours
4. **S3 Lifecycle Policies**: Archive old logs to Glacier
5. **CloudWatch Logs Retention**: Reduce from 30 to 7 days for dev

## Troubleshooting

### ECS Tasks Not Starting

```bash
# Check task status
aws ecs describe-tasks \
  --cluster rampart-cluster \
  --tasks $(aws ecs list-tasks --cluster rampart-cluster --query 'taskArns[0]' --output text)

# Common issues:
# - Image not found in ECR → Push image
# - Secrets not accessible → Check IAM permissions
# - Health check failing → Check /health endpoint
```

### Database Connection Issues

```bash
# Test from ECS task
aws ecs execute-command \
  --cluster rampart-cluster \
  --task <task-id> \
  --container rampart-api \
  --interactive \
  --command "/bin/bash"

# Inside container
curl localhost:8000/health
```

### High Costs

```bash
# Check cost breakdown
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=SERVICE
```

## Cleanup

To destroy all resources:

```bash
# WARNING: This will delete everything including databases
terraform destroy

# To keep backups, take manual snapshots first
aws rds create-db-cluster-snapshot \
  --db-cluster-identifier rampart-cluster \
  --db-cluster-snapshot-identifier rampart-final-backup
```

## Security Best Practices

1. **Enable HTTPS**: Add ACM certificate and update ALB listener
2. **Restrict Security Groups**: Limit access to specific IPs
3. **Enable VPC Flow Logs**: Monitor network traffic
4. **Rotate Secrets**: Enable automatic rotation in Secrets Manager
5. **Enable GuardDuty**: Threat detection service
6. **Use WAF**: Add AWS WAF to ALB for DDoS protection

## Next Steps

1. **Add HTTPS**: Configure ACM certificate and update ALB
2. **Setup Monitoring**: Create CloudWatch dashboards and alarms
3. **Configure Backups**: Test restore procedures
4. **Add Bastion Host**: For secure database access
5. **Multi-Region**: Deploy to multiple regions for HA
6. **CDN**: Add CloudFront for frontend assets

## Support

For issues or questions:
- Check CloudWatch Logs: `/ecs/rampart-backend`
- Review ECS service events
- Consult AWS documentation: https://docs.aws.amazon.com/
