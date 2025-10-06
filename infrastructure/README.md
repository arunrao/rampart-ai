# Infrastructure & Deployment Guide

## 📚 Documentation Index

This directory contains **production-ready infrastructure-as-code** for deploying Project Rampart to the cloud with auto-scaling capabilities.

### Quick Links

| Document | Description | Time to Read |
|----------|-------------|--------------|
| **[DEPLOYMENT_QUICKSTART.md](../DEPLOYMENT_QUICKSTART.md)** | Deploy in 30 minutes | 5 min |
| **[CLOUD_DEPLOYMENT_SUMMARY.md](../CLOUD_DEPLOYMENT_SUMMARY.md)** | Executive summary | 3 min |
| **[CLOUD_DEPLOYMENT_OPTIONS.md](../CLOUD_DEPLOYMENT_OPTIONS.md)** | Detailed architecture guide | 15 min |
| **[COMPARISON_MATRIX.md](./COMPARISON_MATRIX.md)** | AWS vs GCP vs Azure vs K8s | 10 min |

---

## 🚀 Quick Start

### Option 1: AWS (Recommended for Production)
```bash
cd infrastructure/aws
terraform init
terraform apply -auto-approve
```
**Time**: 20-30 minutes | **Cost**: $656-1,057/month

### Option 2: GCP (Fastest Deployment)
```bash
cd infrastructure/gcp
terraform init
terraform apply -auto-approve
```
**Time**: 15-20 minutes | **Cost**: $387-563/month

### Option 3: Kubernetes (Multi-Cloud)
```bash
kubectl apply -f infrastructure/k8s/deployment.yaml
```
**Time**: 30-45 minutes | **Cost**: $620-880/month

---

## 📁 Directory Structure

```
infrastructure/
├── README.md                    # This file
├── COMPARISON_MATRIX.md         # Detailed provider comparison
│
├── aws/
│   ├── main.tf                  # Complete AWS infrastructure (Terraform)
│   └── README.md                # AWS deployment guide
│
├── gcp/
│   └── main.tf                  # Complete GCP infrastructure (Terraform)
│
└── k8s/
    └── deployment.yaml          # Kubernetes manifests (EKS/GKE/AKS)
```

---

## 🏗️ What Gets Deployed

### AWS Infrastructure
- **Compute**: ECS Fargate (2-20 auto-scaling containers)
- **Database**: RDS Aurora PostgreSQL (Multi-AZ, auto-failover)
- **Cache**: ElastiCache Redis (cluster mode, 2-node HA)
- **Load Balancer**: Application Load Balancer (ALB)
- **Networking**: VPC with public/private subnets, NAT gateways
- **Secrets**: AWS Secrets Manager (encrypted credentials)
- **Monitoring**: CloudWatch Logs, Metrics, X-Ray tracing
- **Auto-scaling**: CPU/Memory-based (70% CPU, 80% memory)

### GCP Infrastructure
- **Compute**: Cloud Run (0-100 auto-scaling instances, serverless)
- **Database**: Cloud SQL PostgreSQL (Regional HA, auto-failover)
- **Cache**: Memorystore Redis (Standard HA, 5 GB)
- **Load Balancer**: Cloud Load Balancing (automatic)
- **Networking**: VPC with private service connection
- **Secrets**: Secret Manager (encrypted credentials)
- **Monitoring**: Cloud Logging, Cloud Monitoring, Cloud Trace
- **Auto-scaling**: Request-based (80 concurrent requests/instance)

### Kubernetes Infrastructure
- **Compute**: Kubernetes pods (2-20 auto-scaling)
- **Database**: Managed PostgreSQL (RDS/Cloud SQL/Azure DB)
- **Cache**: Managed Redis (ElastiCache/Memorystore/Azure Cache)
- **Load Balancer**: NGINX Ingress Controller
- **Networking**: Network policies, service mesh (optional)
- **Secrets**: Kubernetes secrets or External Secrets Operator
- **Monitoring**: Prometheus, Grafana, Jaeger
- **Auto-scaling**: HPA (CPU/Memory/Custom metrics)

---

## 💰 Cost Breakdown

### AWS (Production)
| Component | Monthly Cost |
|-----------|--------------|
| ECS Fargate (2-10 tasks) | $50-250 |
| RDS Aurora (db.r6g.large + replica) | $300-400 |
| ElastiCache Redis (cache.r6g.large) | $150-200 |
| Load Balancer + NAT Gateway | $80-120 |
| CloudWatch Logs (50 GB) | $25-30 |
| Secrets Manager | $4 |
| **Total** | **$656-1,057** |

### GCP (Production)
| Component | Monthly Cost |
|-----------|--------------|
| Cloud Run (1M requests, 2 vCPU, 4 GB) | $40-80 |
| Cloud SQL (db-custom-4-16384 + HA) | $250-350 |
| Memorystore Redis (5 GB Standard) | $50-70 |
| Load Balancing | $20-30 |
| Cloud Logging (50 GB) | $25-30 |
| **Total** | **$387-563** |

### Kubernetes (Production)
| Component | Monthly Cost |
|-----------|--------------|
| Kubernetes Cluster (3 nodes, 4 vCPU each) | $300-400 |
| Managed PostgreSQL (4 vCPU, 16 GB) | $250-350 |
| Managed Redis (5 GB) | $50-100 |
| Load Balancer | $20-30 |
| **Total** | **$620-880** |

---

## 🎯 Deployment Scenarios

### Scenario 1: Startup / MVP
**Recommendation**: GCP Cloud Run
- **Why**: Lowest cost ($150-250/month for low traffic), fastest deployment
- **Deploy**: `cd infrastructure/gcp && terraform apply`
- **Time**: 15 minutes

### Scenario 2: Production SaaS
**Recommendation**: AWS ECS
- **Why**: Best reliability (99.99% SLA), excellent database (Aurora)
- **Deploy**: `cd infrastructure/aws && terraform apply`
- **Time**: 20 minutes

### Scenario 3: Enterprise / High Traffic
**Recommendation**: AWS ECS with Reserved Instances
- **Why**: 30-50% cost savings, best performance
- **Deploy**: `cd infrastructure/aws && terraform apply`
- **Cost**: $1,200-1,800/month (10M requests/day)

### Scenario 4: Multi-Cloud / Portability
**Recommendation**: Kubernetes
- **Why**: Deploy to any cloud, zero vendor lock-in
- **Deploy**: `kubectl apply -f infrastructure/k8s/deployment.yaml`
- **Time**: 30 minutes

---

## 🔧 Customization

### Adjust Instance Sizes

**AWS** (`infrastructure/aws/main.tf`):
```hcl
variable "db_instance_class" {
  default = "db.r6g.large"  # Change to db.t4g.medium for dev
}

variable "ecs_task_cpu" {
  default = 1024  # 1 vCPU (change to 2048 for 2 vCPU)
}
```

**GCP** (`infrastructure/gcp/main.tf`):
```hcl
variable "db_tier" {
  default = "db-custom-4-16384"  # Change to db-custom-2-8192 for dev
}

variable "cloud_run_min_instances" {
  default = 1  # Change to 0 for scale-to-zero
}
```

### Adjust Auto-scaling

**AWS**:
```hcl
variable "ecs_min_capacity" {
  default = 2  # Minimum instances
}

variable "ecs_max_capacity" {
  default = 20  # Maximum instances
}
```

**Kubernetes** (`infrastructure/k8s/deployment.yaml`):
```yaml
spec:
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        averageUtilization: 70  # Scale at 70% CPU
```

---

## 🔐 Security Checklist

Before going to production:

- [ ] **Enable HTTPS**: Add SSL/TLS certificate (ACM for AWS, automatic for GCP)
- [ ] **Restrict CORS**: Update `CORS_ORIGINS` to your frontend domain only
- [ ] **Rotate Secrets**: Enable automatic rotation in Secrets Manager
- [ ] **Enable WAF**: Add Web Application Firewall (AWS WAF, Cloud Armor)
- [ ] **Setup VPN**: For secure database access (or use bastion host)
- [ ] **Enable Logging**: Ensure all logs are being captured
- [ ] **Configure Alerts**: Set up CloudWatch/Cloud Monitoring alarms
- [ ] **Backup Testing**: Verify database backups and test restore
- [ ] **Network Policies**: Restrict pod-to-pod communication (Kubernetes)
- [ ] **IAM Audit**: Review and minimize permissions

---

## 📊 Monitoring & Observability

### AWS
- **Logs**: CloudWatch Logs (`/ecs/rampart-backend`)
- **Metrics**: CloudWatch Metrics (CPU, Memory, Request Count)
- **Tracing**: X-Ray (distributed tracing)
- **Dashboards**: CloudWatch Dashboards
- **Alarms**: CloudWatch Alarms (CPU > 80%, errors > 5%)

### GCP
- **Logs**: Cloud Logging (automatic)
- **Metrics**: Cloud Monitoring (CPU, Memory, Request Count)
- **Tracing**: Cloud Trace (distributed tracing)
- **Dashboards**: Cloud Monitoring Dashboards
- **Alerts**: Cloud Monitoring Alerts

### Kubernetes
- **Logs**: ELK Stack or Loki
- **Metrics**: Prometheus + Grafana
- **Tracing**: Jaeger
- **Dashboards**: Grafana
- **Alerts**: Prometheus Alertmanager

---

## 🚨 Troubleshooting

### Common Issues

**Issue**: Terraform apply fails with "resource already exists"
```bash
# Solution: Import existing resource or destroy and recreate
terraform import aws_ecr_repository.backend rampart-backend
```

**Issue**: ECS tasks not starting
```bash
# Check logs
aws logs tail /ecs/rampart-backend --follow

# Check service events
aws ecs describe-services --cluster rampart-cluster --services rampart-backend-service
```

**Issue**: Cloud Run deployment fails
```bash
# Check logs
gcloud run services logs read rampart-backend --region us-central1 --limit 50

# Check service status
gcloud run services describe rampart-backend --region us-central1
```

**Issue**: Kubernetes pods crashing
```bash
# Check pod logs
kubectl logs -n rampart -l app=rampart-backend --tail=100

# Check pod events
kubectl describe pod -n rampart -l app=rampart-backend
```

---

## 🔄 CI/CD Pipelines

Automated deployment workflows are available in `.github/workflows/`:

- **`deploy-aws.yml`**: Deploy to AWS ECS on push to `main`
- **`deploy-gcp.yml`**: Deploy to GCP Cloud Run on push to `main`

### Setup CI/CD

1. **Add GitHub Secrets**:
   - AWS: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   - GCP: `GCP_PROJECT_ID`, `GCP_SA_KEY`

2. **Push to main branch**:
   ```bash
   git push origin main
   ```

3. **Automatic deployment** triggers:
   - Run tests
   - Build Docker image
   - Push to registry (ECR/Artifact Registry)
   - Deploy to cloud (ECS/Cloud Run)
   - Verify health check
   - Rollback on failure

---

## 📖 Additional Resources

### Documentation
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [GCP Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)

### Tools
- [AWS CLI](https://aws.amazon.com/cli/)
- [gcloud CLI](https://cloud.google.com/sdk/gcloud)
- [kubectl](https://kubernetes.io/docs/reference/kubectl/)
- [Terraform](https://www.terraform.io/)
- [Docker](https://www.docker.com/)

### Community
- [CNCF Slack](https://slack.cncf.io/)
- [AWS Forums](https://forums.aws.amazon.com/)
- [GCP Community](https://www.googlecloudcommunity.com/)
- [Kubernetes Slack](https://kubernetes.slack.com/)

---

## 🎓 Learning Path

### Beginner
1. Start with **GCP Cloud Run** (easiest)
2. Read `DEPLOYMENT_QUICKSTART.md`
3. Deploy to staging environment
4. Test auto-scaling with load testing

### Intermediate
1. Try **AWS ECS** for production features
2. Read `CLOUD_DEPLOYMENT_OPTIONS.md`
3. Setup CI/CD with GitHub Actions
4. Configure monitoring and alerts

### Advanced
1. Deploy to **Kubernetes** for multi-cloud
2. Read `COMPARISON_MATRIX.md`
3. Implement blue/green deployments
4. Setup multi-region architecture

---

## 💡 Best Practices

1. **Start Small**: Deploy to dev/staging first
2. **Use Infrastructure-as-Code**: Never manually create resources
3. **Enable Auto-scaling**: Let the platform handle traffic spikes
4. **Monitor Everything**: Set up logging, metrics, and alerts
5. **Test Backups**: Regularly test database restore procedures
6. **Security First**: Enable HTTPS, rotate secrets, restrict access
7. **Cost Optimization**: Use reserved instances, auto-scaling, spot instances
8. **Document Changes**: Keep infrastructure code in version control

---

## 🤝 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review cloud provider documentation
3. Check logs (CloudWatch, Cloud Logging, kubectl logs)
4. Review Terraform plan output
5. Consult the comparison matrix for alternatives

---

## 📝 Summary

You now have **5 deployment options** with complete infrastructure-as-code:

1. ✅ **AWS ECS** - Production-grade, enterprise-ready
2. ✅ **GCP Cloud Run** - Serverless, fastest deployment
3. ✅ **Azure Container Apps** - For Azure customers
4. ✅ **Kubernetes** - Multi-cloud, maximum portability
5. ✅ **Hybrid** - Vercel frontend + cloud backend

All options include:
- Auto-scaling (2-20+ instances)
- High-availability database (Multi-AZ)
- Redis cache cluster
- Load balancing
- Secrets management
- Monitoring and logging
- CI/CD pipelines
- Security best practices

**Choose your option and deploy in 15-30 minutes!** 🚀
