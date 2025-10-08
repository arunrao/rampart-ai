# 🚀 Project Rampart - Quick Start Guide

## Prerequisites (5 minutes)

1. **AWS Account** with credit card

2. **Get AWS Access Keys**:
   - Go to [IAM Console](https://console.aws.amazon.com/iam/)
   - Users → Create user → Create access keys
   - **📖 See [AWS_CREDENTIALS_GUIDE.md](AWS_CREDENTIALS_GUIDE.md) for detailed steps**
   - Save your Access Key ID and Secret Access Key

3. **Install AWS CLI**:
   ```bash
   # Mac
   brew install awscli
   
   # Linux
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip
   sudo ./aws/install
   ```

4. **Configure AWS CLI**:
   ```bash
   aws configure
   # Enter your AWS Access Key ID (from step 2)
   # Enter your AWS Secret Access Key (from step 2)
   # Default region: us-east-1
   # Default output format: json
   
   # Verify it works:
   aws sts get-caller-identity
   ```

5. **Create EC2 Key Pair** in AWS Console:
   - Go to EC2 → Key Pairs → Create key pair
   - Name: `rampart-key`
   - Download and save the `.pem` file

6. **Google OAuth Setup**:
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Create new project or select existing
   - APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
   - Application type: Web application
   - Save Client ID and Client Secret (you'll add redirect URIs after deployment)

## Deploy (10 minutes)

```bash
# 1. Navigate to the aws directory
cd aws

# 2. Run the setup wizard (one time only)
./setup.sh
# This will:
# - Check prerequisites (AWS CLI, Docker, credentials)
# - Prompt for all configuration values
# - Create a .env file with your settings

# 3. Load environment variables
source .env

# 4. Deploy to AWS
./deploy.sh
```

**Wait 15 minutes for deployment to complete.**

## Post-Deployment (5 minutes)

### 1. Update Google OAuth Redirect URIs

After deployment completes, you'll see:
```
Frontend: http://rampart-alb-xxx.us-east-1.elb.amazonaws.com
Backend API: http://rampart-alb-xxx.us-east-1.elb.amazonaws.com/api/v1
```

Go to [Google Cloud Console](https://console.cloud.google.com/):
1. APIs & Services → Credentials → Click your OAuth Client ID
2. Add to **Authorized JavaScript origins**:
   ```
   http://rampart-alb-xxx.us-east-1.elb.amazonaws.com
   ```
3. Add to **Authorized redirect URIs**:
   ```
   http://rampart-alb-xxx.us-east-1.elb.amazonaws.com/api/v1/auth/google/callback
   ```
4. Click **Save**

### 2. Access Your Application

Wait 5 more minutes for the application to start, then visit:
```
http://rampart-alb-xxx.us-east-1.elb.amazonaws.com
```

Click **Sign in with Google** and log in!

## Common Commands

```bash
# Update application after code changes
./update.sh

# View logs
./logs.sh

# Delete everything
./cleanup.sh
```

## Troubleshooting

### Can't access the application?

Wait 10-15 minutes after deployment completes. The EC2 instance needs time to:
1. Start up
2. Download Docker images
3. Start containers

### Google OAuth not working?

1. Make sure you updated the redirect URIs in Google Console
2. Use the exact URL from the deployment output
3. Wait a few minutes after updating Google settings

### Still having issues?

```bash
# Check if CloudFormation stack completed
aws cloudformation describe-stacks --stack-name rampart-production

# Get instance public IP
aws ec2 describe-instances \
  --filters "Name=tag:aws:autoscaling:groupName,Values=rampart-production-asg" \
  --query 'Reservations[*].Instances[*].PublicIpAddress' \
  --output text

# SSH into instance (replace with your IP)
ssh -i rampart-key.pem ubuntu@<INSTANCE_IP>

# Check Docker containers
docker ps
docker-compose logs
```

## What You Just Created

- ✅ Scalable web application on AWS
- ✅ PostgreSQL database with automated backups
- ✅ Load balancer for high availability
- ✅ Secure secrets management
- ✅ Auto-scaling infrastructure
- ✅ CloudWatch monitoring

**Monthly Cost:** ~$60-70 (can be reduced with Reserved Instances)

## Next Steps

1. **Enable HTTPS**: Get a domain and SSL certificate
2. **Set up monitoring**: Configure CloudWatch alarms
3. **Customize**: Modify the application to your needs
4. **Scale**: Increase instance count for production traffic

## Need Help?

See the full [README.md](README.md) for detailed documentation.

---

**That's it! You now have Project Rampart running on AWS! 🎉**
