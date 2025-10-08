# Deployment Guide

## 🚀 Deploy to AWS (Automated)

Complete deployment with CloudFormation - no manual AWS Console steps needed!

### Quick Start

```bash
cd aws
./setup.sh      # Interactive setup wizard
source .env     # Load configuration
./deploy.sh     # Deploy to AWS (~15 min)
```

**See [aws/QUICKSTART.md](aws/QUICKSTART.md) for detailed instructions.**

---

## 📝 What You Need

1. **AWS Account** - with billing enabled
2. **AWS Access Keys** - for AWS CLI ([see guide](aws/AWS_CREDENTIALS_GUIDE.md))
3. **AWS CLI** - installed and configured (`aws configure`)
4. **Docker** - installed locally
5. **EC2 Key Pair** - for SSH access ([create one](https://console.aws.amazon.com/ec2/home#KeyPairs:))
6. **Google OAuth** - Client ID & Secret ([get them](https://console.cloud.google.com/apis/credentials))

---

## 💻 Local Development

To run locally with Docker Compose:

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

Access the application:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api/v1/docs

---

## 📚 Documentation

- **[aws/QUICKSTART.md](aws/QUICKSTART.md)** - Get started in 5 minutes
- **[aws/README.md](aws/README.md)** - Complete AWS deployment guide
- **[aws/.env.example](aws/.env.example)** - Configuration template

---

## 🔧 Post-Deployment

After deploying, update your Google OAuth redirect URIs:

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Add your ALB URL (shown after deployment) to:
   - Authorized JavaScript origins
   - Authorized redirect URIs

---

## 💰 Costs

AWS deployment with default settings: **~$60-70/month**

- EC2 t3.medium: ~$30
- RDS db.t3.micro: ~$15
- Load Balancer: ~$16
- Other (storage, data transfer): ~$5

**Reduce costs:**
- Use t3.small instead of t3.medium: Save $15/month
- Use Reserved Instances: Save 30-70%

---

## 🛠️ Common Operations

```bash
cd aws

# Update application code
./update.sh

# View logs
./logs.sh

# Delete everything
./cleanup.sh
```

---

## 📞 Need Help?

- Check [aws/README.md](aws/README.md) for troubleshooting
- Review CloudFormation events in AWS Console
- Verify prerequisites are met

---

## 📄 Architecture

The CloudFormation template deploys:

```
Internet
   ↓
Application Load Balancer
   ↓
Auto Scaling Group (EC2)
   ├── Frontend (Next.js)
   └── Backend (FastAPI)
        ↓
   RDS PostgreSQL
```

All resources are in a VPC with proper security groups and monitoring.
