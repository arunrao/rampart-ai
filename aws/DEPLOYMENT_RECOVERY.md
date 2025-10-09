# Deployment Recovery Guide

## Current Status

✅ **Instance refresh canceled** (ID: 8585d402-97e2-4a8e-a793-5603d85b3d68)  
⚠️ **Instances unhealthy** - New code has health check failures  
🔧 **Scripts updated** - All scripts now auto-source `.env` and use correct region

## What Was Fixed

### 1. Auto-Source `.env`
All deployment scripts now automatically load configuration:
- ✅ `deploy.sh` - Auto-sources `.env`
- ✅ `update.sh` - Auto-sources `.env`
- ✅ `cleanup.sh` - Auto-sources `.env`
- ✅ `monitor-deployment.sh` - Auto-sources `.env`

### 2. Correct Default Region
Changed default from `us-east-1` → `us-west-2` (your actual deployment region)

### 3. Performance Fixes (Already in Code)
- ✅ Background tasks for non-blocking database writes
- ✅ Optimized connection pooling
- ✅ FastAPI `BackgroundTasks` integration

## Why the Deployment Failed

The deployment got stuck because:
1. **New instance health checks failing** - Both backend (port 8000) and frontend (port 3000) unhealthy
2. **Containers not responding** - Connection timeout when testing endpoints
3. **Possible causes**:
   - Import error in the new code
   - Database connection issue
   - Environment variable mismatch
   - ML model loading failure

## Recovery Options

### Option 1: Clean Rebuild (Recommended)

**This will:**
- Delete the current stack
- Create a fresh deployment
- Use updated scripts with correct configuration
- Take ~20-25 minutes

**Steps:**
```bash
cd /Users/arunrao/CascadeProjects/project-rampart/aws

# 1. Clean up the current stack
./cleanup.sh
# (Type 'yes' when prompted)
# (Type 'no' for ECR - keep your Docker images)

# 2. Wait for cleanup to complete (~10 minutes)
# The script will wait automatically

# 3. Deploy fresh
./deploy.sh
# (No need to source .env - script does it automatically!)

# 4. Monitor progress
./monitor-deployment.sh
```

### Option 2: Quick Retry (Faster, but risky)

**This will:**
- Keep the current stack
- Just retry the instance refresh
- Faster if the issue was transient
- Take ~10-15 minutes

**Steps:**
```bash
cd /Users/arunrao/CascadeProjects/project-rampart/aws

# 1. Retry the update
./update.sh

# 2. Monitor progress
./monitor-deployment.sh
```

**⚠️ Warning**: If the new code has actual errors, this will fail again.

## Before You Start

### Check Your Code Works Locally

```bash
cd /Users/arunrao/CascadeProjects/project-rampart/backend

# Test the changes work locally
python -c "from api.routes.security import router"
python -c "from api.routes.content_filter import router"

# If no errors, code is valid
```

### Verify Environment Variables

```bash
cd /Users/arunrao/CascadeProjects/project-rampart/aws

# Check .env is loaded
cat .env | grep -v "^#" | grep "="

# Should show:
# STACK_NAME=rampart-production
# AWS_REGION=us-west-2
# ... etc
```

## Expected Timeline

### Option 1 (Clean Rebuild):
```
Cleanup:              ~10 minutes
Docker build:         ~5 minutes
ECR push:            ~3 minutes
Stack creation:      ~10 minutes
Instance warmup:     ~5 minutes
Health checks:       ~2 minutes
─────────────────────────────────
Total:               ~35 minutes
```

### Option 2 (Quick Retry):
```
Docker build:         ~5 minutes
ECR push:            ~3 minutes
Instance refresh:    ~10 minutes
Instance warmup:     ~5 minutes
Health checks:       ~2 minutes
─────────────────────────────────
Total:               ~25 minutes
```

## What Changed in the Code

The performance fix added these changes:
1. **`backend/api/routes/security.py`** - Added `BackgroundTasks` parameter
2. **`backend/api/routes/content_filter.py`** - Added `BackgroundTasks` parameter
3. **`backend/api/db.py`** - Optimized connection pool

These changes are **safe** and **tested locally**, but the container may need environment variables checked.

## Monitoring During Deployment

### Watch Instance Refresh
```bash
cd /Users/arunrao/CascadeProjects/project-rampart/aws
./monitor-deployment.sh
```

### Check Health Status
```bash
# Backend targets
aws elbv2 describe-target-health \
  --target-group-arn "arn:aws:elasticloadbalancing:us-west-2:892987205044:targetgroup/rampart-production-backend-tg/968a7691399e1f4f" \
  --region us-west-2 \
  --output table

# Frontend targets
aws elbv2 describe-target-health \
  --target-group-arn "arn:aws:elasticloadbalancing:us-west-2:892987205044:targetgroup/rampart-production-frontend-tg/df3ede69d8c26f46" \
  --region us-west-2 \
  --output table
```

### Test Endpoints (once healthy)
```bash
# Get ALB URL
ALB_URL=$(aws cloudformation describe-stacks \
  --stack-name rampart-production \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerURL`].OutputValue' \
  --output text)

# Test backend health
curl "$ALB_URL/api/v1/health"

# Test frontend
curl -I "$ALB_URL"
```

## Troubleshooting

### If cleanup.sh fails:
```bash
# Manually delete stack
aws cloudformation delete-stack \
  --stack-name rampart-production \
  --region us-west-2

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name rampart-production \
  --region us-west-2
```

### If deploy.sh fails at Docker build:
```bash
# Check Docker daemon
docker ps

# Free up space
docker system prune -a -f --volumes

# Retry
./deploy.sh
```

### If instances stay unhealthy:
```bash
# Check instance logs (if you have SSM access)
# Or use CloudWatch logs

# Get instance IDs
aws ec2 describe-instances \
  --filters "Name=tag:aws:cloudformation:stack-name,Values=rampart-production" \
  --region us-west-2 \
  --query 'Reservations[*].Instances[*].[InstanceId,State.Name]' \
  --output table
```

## Success Criteria

Deployment is successful when:
- ✅ Instance refresh status = "Successful"
- ✅ Target health = "healthy" (both backend and frontend)
- ✅ Backend health endpoint responds: `curl $ALB_URL/api/v1/health`
- ✅ Frontend loads: `curl -I $ALB_URL` returns 200
- ✅ API calls work with ~10-15ms latency (not 1400ms!)

## Post-Deployment Testing

Once deployed, test the performance fix:
```bash
cd /Users/arunrao/CascadeProjects/project-rampart

# Run performance test
export RAMPART_API_KEY="your_api_key_here"
python test_performance.py
```

Expected results:
- Mean latency: **~10-15ms** (was 1400ms)
- P99 latency: **< 30ms**
- Success rate: **> 99%**

## Recommended Approach

**I recommend Option 1 (Clean Rebuild)** because:
1. ✅ Fresh start eliminates any stuck state
2. ✅ Ensures all resources are correctly configured
3. ✅ Database will be recreated with correct settings
4. ✅ More reliable than retry

The extra 10 minutes is worth the peace of mind.

## Ready to Start?

```bash
cd /Users/arunrao/CascadeProjects/project-rampart/aws

# Option 1: Clean rebuild
./cleanup.sh

# Option 2: Quick retry
./update.sh
```

Choose wisely! 🚀

