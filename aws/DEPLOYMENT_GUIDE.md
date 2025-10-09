# Deployment Guide - Zero-Downtime Deployments

## Quick Commands

### Deploy Code Changes
```bash
cd aws/
./update.sh                    # Zero-downtime deployment (10-15 min)
./monitor-deployment.sh        # Track progress (optional)
```

### Deploy Infrastructure Changes
```bash
cd aws/
./deploy.sh rampart.arunrao.com
```

### Monitor & Debug
```bash
./logs.sh                      # View application logs
./monitor-deployment.sh        # Track deployment progress
```

### Emergency: Cancel Deployment
```bash
ASG_NAME="rampart-production-asg"
aws autoscaling cancel-instance-refresh \
  --auto-scaling-group-name $ASG_NAME \
  --region us-west-2
```

### ⚠️ DO NOT DO
❌ `docker-compose restart backend`  
❌ `docker-compose up -d backend`  
❌ Direct SSM commands to restart containers  

### ✅ ALWAYS DO
✅ Use `./update.sh` for deployments  
✅ Monitor with `./monitor-deployment.sh`  
✅ Wait for deployment to complete (10-15 min)  

---

## Overview

Project Rampart uses **AWS Auto Scaling Group Instance Refresh** for zero-downtime deployments. This ensures:
- ✅ **No service interruption** - Always maintains healthy instances
- ✅ **ML model warmup** - 5-minute grace period for model loading
- ✅ **Health check compliance** - Instances only serve traffic when ready
- ✅ **Automatic rollback** - Failed instances are replaced automatically

## Why Instance Refresh?

### ❌ **DO NOT** Restart Containers Directly

**Problem with direct container restarts:**
```bash
# ❌ DON'T DO THIS - Causes cascading failures
docker-compose restart backend
docker-compose up -d backend
```

**What happens:**
1. Container restarts → ML models reload (2 minutes)
2. Health checks fail after 90 seconds
3. ALB marks instance unhealthy
4. ASG terminates the "unhealthy" instance
5. New instance launches → repeats cycle
6. Result: Continuous instance replacement, service degradation

### ✅ **DO** Use Instance Refresh

**Correct approach:**
```bash
./update.sh
```

**What happens:**
1. Build & push new images to ECR
2. Trigger instance refresh
3. ASG launches new instances with updated images
4. Waits 5 minutes for ML models to load
5. New instances pass health checks
6. Old instances gracefully drained and terminated
7. Result: Zero downtime, smooth deployment

## Deployment Scripts

### 1. **Regular Updates** (Code Changes Only)

Use when you've made code changes but NOT infrastructure changes:

```bash
cd aws/
./update.sh
```

**What it does:**
- Builds backend & frontend Docker images
- Pushes images to ECR
- Triggers instance refresh
- Takes 10-15 minutes

**Monitor progress:**
```bash
./monitor-deployment.sh
```

### 2. **Full Deployment** (Infrastructure + Code)

Use when you've changed CloudFormation template or initial deployment:

```bash
cd aws/
./deploy.sh rampart.arunrao.com
```

**What it does:**
- Updates CloudFormation stack
- Updates infrastructure (if changed)
- Updates Launch Template
- Triggers instance refresh automatically
- Takes 15-20 minutes

### 3. **Monitor Deployment**

Track the progress of an ongoing deployment:

```bash
./monitor-deployment.sh
```

**Shows:**
- Current status (InProgress, Successful, Failed)
- Progress percentage
- Instances being updated
- Real-time health check status

## Instance Refresh Configuration

Current settings in `update.sh`:

```json
{
  "MinHealthyPercentage": 50,      // Keep 50% healthy during rollout
  "InstanceWarmup": 300,            // Wait 5 minutes for ML models
  "CheckpointPercentages": [50, 100], // Pause at 50% and 100%
  "CheckpointDelay": 60,            // Wait 60s at checkpoints
  "SkipMatching": false             // Always refresh all instances
}
```

### Why These Settings?

- **MinHealthyPercentage: 50%**
  - With 2+ instances: Always keep at least 1 healthy
  - Ensures service availability during deployment
  
- **InstanceWarmup: 300s (5 minutes)**
  - DeBERTa model loading: ~15 seconds
  - GLiNER model loading: ~15 seconds
  - ONNX optimization: ~12 seconds
  - Container startup: ~30 seconds
  - Buffer time: ~4 minutes
  - Total: 5 minutes (safe margin)
  
- **CheckpointPercentages: [50, 100]**
  - Pause after 50% of instances updated
  - Verify everything works before continuing
  - Manual verification opportunity

## Health Check Configuration

### Backend Health Check
```yaml
Path: /api/v1/health
Interval: 30 seconds
Timeout: 5 seconds
Healthy Threshold: 2 consecutive successes
Unhealthy Threshold: 3 consecutive failures
Time to Unhealthy: 90 seconds (3 × 30s)
```

### Why ML Models Cause Issues

**Timeline:**
```
t=0s:   Container starts
t=30s:  Health check #1 fails (models loading)
t=60s:  Health check #2 fails (models loading)
t=90s:  Health check #3 fails (models still loading)
t=90s:  ❌ MARKED UNHEALTHY (but models need 120s!)
t=120s: Models ready, but too late - already unhealthy
```

**Solution: Instance Warmup**
- ASG ignores health checks for first 300 seconds
- Gives models time to load before health checks matter
- Prevents premature termination

## Troubleshooting

### Issue: Instances Keep Getting Replaced

**Symptoms:**
- Multiple instances launching and terminating
- 503 Service Unavailable errors
- "Draining" instances in target group

**Cause:** Someone restarted containers directly (bypassing instance refresh)

**Fix:**
1. Cancel any ongoing instance refresh:
   ```bash
   ASG_NAME="rampart-production-asg"
   aws autoscaling cancel-instance-refresh \
     --auto-scaling-group-name $ASG_NAME \
     --region us-west-2
   ```

2. Wait for current instances to stabilize (5 minutes)

3. Deploy properly using `./update.sh`

### Issue: Deployment Stuck at 50%

**Symptoms:**
- Progress shows 50% for a long time
- New instance is healthy but deployment paused

**Cause:** Checkpoint delay - waiting for manual verification

**Resolution:**
- This is normal! The system pauses at 50% for 60 seconds
- Use this time to verify the new instance works correctly
- Test the endpoints, check logs
- Deployment will auto-continue after checkpoint delay

### Issue: Instance Refresh Fails

**Symptoms:**
- Status shows "Failed"
- Instances won't pass health checks

**Possible causes:**
1. ECR image not found
2. UserData script error
3. Docker compose failure
4. Environment variables missing

**Debug:**
```bash
# Check instance logs
INSTANCE_ID="<failing-instance-id>"
aws ssm send-command \
  --instance-ids $INSTANCE_ID \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["tail -100 /var/log/cloud-init-output.log"]' \
  --region us-west-2
```

## Best Practices

### ✅ DO

1. **Always use `./update.sh` for code deployments**
2. **Monitor deployments with `./monitor-deployment.sh`**
3. **Test locally before deploying to production**
4. **Build multi-platform images for AWS (linux/amd64)**
5. **Wait for deployment to complete before next deployment**
6. **Check CloudWatch logs if issues occur**

### ❌ DON'T

1. **Never restart containers directly via SSM**
2. **Never run `docker-compose restart` on production instances**
3. **Never start multiple instance refreshes simultaneously**
4. **Never skip the checkpoint verifications**
5. **Never deploy without testing locally first**
6. **Never ignore failed health checks**

## Manual Verification Checklist

After deployment reaches 50%, verify:

```bash
# 1. Check health endpoint
curl https://rampart.arunrao.com/api/v1/health

# Expected: {"status":"healthy","ml_models":"operational"}

# 2. Check frontend
curl https://rampart.arunrao.com -I

# Expected: HTTP/2 200

# 3. Test prompt injection detection
# (Requires authentication - use UI or API key)

# 4. Check target group health
aws elbv2 describe-target-health \
  --target-group-arn <backend-tg-arn> \
  --region us-west-2
```

## Emergency Rollback

If deployment fails catastrophically:

```bash
# 1. Cancel instance refresh
ASG_NAME="rampart-production-asg"
aws autoscaling cancel-instance-refresh \
  --auto-scaling-group-name $ASG_NAME \
  --region us-west-2

# 2. Rollback ECR images (tag previous version as latest)
# Identify previous working image digest from ECR console
# Or restore from your last known good deployment

# 3. Start new instance refresh with old images
./update.sh
```

## Monitoring Commands

```bash
# Watch instance refresh progress
watch -n 10 'aws autoscaling describe-instance-refreshes \
  --auto-scaling-group-name rampart-production-asg \
  --region us-west-2 \
  --query "InstanceRefreshes[0].[Status,PercentageComplete]" \
  --output table'

# Check target health
aws elbv2 describe-target-health \
  --target-group-arn $(aws elbv2 describe-target-groups \
    --query 'TargetGroups[?contains(TargetGroupName, `backend`)].TargetGroupArn' \
    --output text) \
  --region us-west-2

# View recent logs
./logs.sh
```

## Summary

**Remember:**
- 🚀 Use `./update.sh` for deployments
- ⏳ Deployments take 10-15 minutes (by design)
- 🎯 Instance warmup (5 min) prevents health check failures
- 📊 Monitor with `./monitor-deployment.sh`
- ✋ Never restart containers directly
- 🔄 Instance refresh ensures zero downtime

Questions? Check the logs or AWS Console for detailed information.

