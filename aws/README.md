# Project Rampart - AWS Deployment Guide

Simple, automated deployment to AWS using CloudFormation. Everything is automated - just run one script!

## 🚀 Quick Start

### Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
   ```bash
   aws configure
   ```
3. **Docker** installed locally
4. **EC2 Key Pair** created in your AWS region (for SSH access)
5. **Google OAuth Credentials**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create OAuth 2.0 credentials
   - You'll update the redirect URIs after deployment

### Deploy in 4 Steps

```bash
# 1. Navigate to the aws directory
cd aws

# 2. Run the setup wizard (one time only)
./setup.sh

# 3. Load environment variables
source .env

# 4. Deploy to AWS
./deploy.sh
```

The script will:
- ✅ Build your Docker images
- ✅ Create ECR repositories
- ✅ Push images to ECR
- ✅ Deploy complete infrastructure via CloudFormation:
  - VPC with public/private subnets
  - Application Load Balancer
  - Auto Scaling Group with EC2 instances
  - RDS PostgreSQL database
  - Security groups
  - Secrets Manager for sensitive data
  - CloudWatch monitoring

**Deployment time:** ~15 minutes

### What Gets Created

| Resource | Description | Cost (approx) |
|----------|-------------|---------------|
| EC2 (t3.medium) | Application server | ~$30/month |
| RDS (db.t3.micro) | PostgreSQL database | ~$15/month |
| Application Load Balancer | Load balancing | ~$16/month |
| Data Transfer | ~5GB/month | ~$0.45/month |
| **Total** | | **~$60-70/month** |

## 📋 Configuration

### Using the Setup Wizard (Recommended)

The setup wizard (`setup.sh`) will:
- ✅ Check all prerequisites
- ✅ Validate AWS credentials
- ✅ Prompt for all required values
- ✅ Create a secure `.env` file
- ✅ Show estimated costs

```bash
./setup.sh
source .env
./deploy.sh
```

### Manual Configuration (Advanced)

You can also manually create a `.env` file:

```bash
cp .env.example .env
# Edit .env with your values
source .env
./deploy.sh
```

Required variables:
- `STACK_NAME` - CloudFormation stack name (default: rampart-production)
- `AWS_REGION` - AWS region (default: us-east-1)
- `GOOGLE_CLIENT_ID` - Your Google OAuth Client ID
- `GOOGLE_CLIENT_SECRET` - Your Google OAuth Client Secret
- `DB_PASSWORD` - RDS database password (min 8 characters)
- `KEY_PAIR_NAME` - EC2 key pair name for SSH access
- `INSTANCE_TYPE` - EC2 instance type (default: t3.medium)
- `DOMAIN_NAME` - (Optional) Your custom domain

## 🔧 Post-Deployment Configuration

### 1. Update Google OAuth Redirect URIs

After deployment, you'll see output like:
```
Frontend: http://rampart-alb-123456789.us-east-1.elb.amazonaws.com
Backend API: http://rampart-alb-123456789.us-east-1.elb.amazonaws.com/api/v1
```

Update your Google OAuth settings:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** → **Credentials**
3. Edit your OAuth 2.0 Client ID
4. Add **Authorized JavaScript origins**:
   ```
   http://rampart-alb-123456789.us-east-1.elb.amazonaws.com
   ```
5. Add **Authorized redirect URIs**:
   ```
   http://rampart-alb-123456789.us-east-1.elb.amazonaws.com/api/v1/auth/google/callback
   ```

### 2. Wait for Application Startup

The EC2 instances need 5-10 minutes to:
- Pull Docker images from ECR
- Start the application containers
- Initialize the database

Check status:
```bash
./logs.sh
```

### 3. Access Your Application

Visit the Frontend URL provided in the deployment output.

## 🔄 Common Operations

### Update Application Code

After making code changes:

```bash
./update.sh
```

This will:
1. Build new Docker images
2. Push to ECR
3. Restart containers on all EC2 instances

### View Logs

```bash
./logs.sh
```

Or SSH into an instance:
```bash
ssh -i your-key.pem ubuntu@<instance-public-ip>
cd /opt/rampart
docker-compose logs -f
```

### Scale the Application

Update the Auto Scaling Group:

```bash
aws autoscaling set-desired-capacity \
  --auto-scaling-group-name rampart-production-asg \
  --desired-capacity 3
```

### Access the Database

Get database credentials from Secrets Manager:

```bash
aws secretsmanager get-secret-value \
  --secret-id rampart-production/database \
  --query SecretString \
  --output text | jq
```

Connect to the database:

```bash
# Get RDS endpoint
RDS_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name rampart-production \
  --query 'Stacks[0].Outputs[?OutputKey==`RDSEndpoint`].OutputValue' \
  --output text)

# SSH tunnel through EC2 instance
ssh -i your-key.pem -L 5432:$RDS_ENDPOINT:5432 ubuntu@<instance-public-ip>

# In another terminal, connect with psql
psql -h localhost -U rampart_admin -d rampart_db
```

## 🗑️ Cleanup

To delete all resources:

```bash
./cleanup.sh
```

This will:
- Delete the CloudFormation stack
- Create a final RDS snapshot (retained for 7 days)
- Optionally delete ECR repositories

**Note:** This cannot be undone!

## 🔒 Security Best Practices

The CloudFormation template includes:

✅ **Network Security**
- VPC with isolated private subnets for RDS
- Security groups with least-privilege access
- RDS not publicly accessible

✅ **Data Security**
- RDS encryption at rest
- SSL/TLS for all connections
- Secrets stored in AWS Secrets Manager
- Automated RDS backups (7-day retention)

✅ **Application Security**
- JWT-based authentication
- Google OAuth integration
- Rate limiting
- Input validation

### Additional Recommendations

1. **Enable HTTPS**: Get an SSL certificate from ACM and update the ALB listener
2. **Enable WAF**: Add AWS WAF for DDoS protection
3. **Enable GuardDuty**: For threat detection
4. **Set up CloudWatch Alarms**: For monitoring and alerts
5. **Enable VPC Flow Logs**: For network monitoring

## 📊 Monitoring

### CloudWatch Dashboards

View metrics in the AWS Console:
- EC2 → Auto Scaling Groups → `rampart-production-asg` → Monitoring
- RDS → Databases → `rampart-production-db` → Monitoring
- EC2 → Load Balancers → `rampart-production-alb` → Monitoring

### Key Metrics to Monitor

- **CPU Utilization** (Target: < 70%)
- **Memory Usage** (Target: < 80%)
- **RDS Connections** (Target: < 80% of max)
- **ALB Request Count**
- **ALB Target Response Time**
- **5xx Errors** (Target: 0)

### CloudWatch Alarms

The template creates an alarm for high CPU usage. Add more:

```bash
# High memory alarm
aws cloudwatch put-metric-alarm \
  --alarm-name rampart-high-memory \
  --alarm-description "Alert when memory exceeds 80%" \
  --metric-name MemoryUtilization \
  --namespace CWAgent \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold
```

## 🐛 Troubleshooting

### Application won't start

1. Check CloudFormation events:
   ```bash
   aws cloudformation describe-stack-events --stack-name rampart-production
   ```

2. Check EC2 instance logs:
   ```bash
   # Get instance ID
   aws ec2 describe-instances \
     --filters "Name=tag:aws:autoscaling:groupName,Values=rampart-production-asg" \
     --query 'Reservations[*].Instances[*].InstanceId' \
     --output text
   
   # View system logs
   aws ec2 get-console-output --instance-id <instance-id>
   ```

3. SSH into instance and check Docker:
   ```bash
   ssh -i your-key.pem ubuntu@<instance-ip>
   docker ps
   docker-compose logs
   ```

### Cannot access application

1. Check security group rules
2. Verify ALB target health:
   ```bash
   aws elbv2 describe-target-health \
     --target-group-arn <target-group-arn>
   ```
3. Check if containers are running:
   ```bash
   ssh -i your-key.pem ubuntu@<instance-ip>
   docker ps
   ```

### Database connection issues

1. Check RDS status:
   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier rampart-production-db
   ```

2. Verify security group allows connection from EC2
3. Check database credentials in Secrets Manager

### Google OAuth not working

1. Verify redirect URIs in Google Console match your ALB URL
2. Check CORS settings in backend
3. Verify Google OAuth credentials in Secrets Manager

## 📚 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Internet                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │      Route53   │ (Optional)
              │   DNS Record   │
              └────────┬───────┘
                       │
                       ▼
              ┌────────────────┐
              │       ALB      │
              │  Load Balancer │
              └────┬───────┬───┘
                   │       │
        ┌──────────┘       └──────────┐
        ▼                              ▼
   ┌────────┐                     ┌────────┐
   │   EC2  │                     │   EC2  │
   │Frontend│                     │Backend │
   │  :3000 │                     │  :8000 │
   └────────┘                     └────┬───┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │   RDS Postgres │
                              │   (Private)    │
                              └────────────────┘
```

## 💡 Cost Optimization

### For Development/Testing

Use smaller instance types:
```bash
# Edit cloudformation/infrastructure.yaml
# Change InstanceType parameter default to t3.small
```

### For Production

1. **Use Reserved Instances** for predictable workloads (save 30-70%)
2. **Enable Auto Scaling** based on demand
3. **Use RDS Reserved Instances** for database
4. **Enable S3 for static assets** (cheaper than serving from EC2)
5. **Use CloudFront CDN** for global distribution

## 🔄 CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Update application
        run: |
          cd aws
          ./update.sh
```

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review CloudFormation events and logs
3. Check AWS service health dashboard
4. Open an issue in the repository

## 📄 License

[Your License Here]
