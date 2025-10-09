# Fast Deployment Strategies for Rampart AI

## Problem: Slow Deployments (10-15 minutes)

**Root cause**: ML models (DeBERTa ~300MB, GLiNER ~200MB) are downloaded every deployment.

**Current timeline**:
- Image build: 2-3 min (downloading models)
- ECR push: 2-3 min (uploading 2GB image)
- Instance launch: 2-3 min
- Container start + model loading: 3-5 min
- **Total: 10-15 minutes**

---

## Strategy 1: Multi-Stage Docker Build ⚡ (RECOMMENDED)

**Time saved: 5-7 minutes → 3-5 minute deployments**

### How It Works

1. **Base Image** (built once per month): Contains all ML models
2. **App Image** (built every deployment): Contains only your code

### Implementation

#### One-time setup (15 minutes):

```bash
cd aws
source .env

# Build base image with models (do this ONCE)
./build-base-image.sh
```

#### Every code deployment (3-5 minutes):

```bash
cd aws
source .env

# Deploy code changes using base image
./update-fast.sh
```

### Benefits

- ✅ **67% faster deployments** (5 min → 3 min)
- ✅ Models already in base image (no download)
- ✅ Smaller app images (~100MB vs 2GB)
- ✅ Faster ECR push/pull
- ✅ Reduced warmup time (180s vs 300s)

### When to Rebuild Base

Only rebuild base image when:
- Adding new ML models
- Updating model versions
- Changing Python dependencies
- Typical frequency: **Once per month**

---

## Strategy 2: Enable GLiNER Pre-download

**Current state**: GLiNER model is downloaded on first API call  
**Fix**: Pre-download in Dockerfile

Edit `backend/Dockerfile` line 30:

```dockerfile
# Uncomment this line:
RUN python -c "from models.pii_detector_gliner import get_gliner_detector; get_gliner_detector(model_type='balanced').detect('warmup')" || true
```

**Time saved**: 30-60 seconds per deployment

---

## Strategy 3: Reduce InstanceWarmup Time

**Current**: 300 seconds (5 minutes) warmup  
**Optimized**: 180 seconds (3 minutes) with base image

When using base image, models are pre-loaded, so you can reduce warmup:

Edit `aws/update-fast.sh` line 109:
```json
"InstanceWarmup": 180  // Reduced from 300
```

**Time saved**: 2 minutes per deployment

---

## Strategy 4: Use ECS/Fargate Instead of EC2 (Advanced)

**Current**: EC2 instances with instance refresh  
**Alternative**: ECS Fargate with rolling updates

### Benefits

- ✅ Update containers, not instances (30-60 seconds)
- ✅ No instance warmup needed
- ✅ No SSH/instance management
- ✅ Auto-scaling at container level

### Drawbacks

- ❌ Higher cost (~$40-50/month vs $30/month)
- ❌ Requires infrastructure migration
- ❌ Different monitoring setup

**Time saved**: 8-10 minutes per deployment (1-2 min total)

---

## Strategy 5: Use Persistent Model Cache (EFS)

Mount an EFS volume to `/app/.cache/huggingface` to persist models across deployments.

### Benefits

- ✅ Models downloaded once, reused forever
- ✅ No rebuild needed for base image

### Drawbacks

- ❌ EFS cost (~$5-10/month)
- ❌ Slower first load (EFS latency)
- ❌ More complex setup

**Time saved**: 2-3 minutes per deployment

---

## Recommended Approach

### For Most Users: Multi-Stage Build (Strategy 1)

**Setup**:
```bash
# One-time (15 min)
cd aws
source .env
./build-base-image.sh

# Every deployment (3-5 min)
source .env
./update-fast.sh
```

**Benefits**:
- Simple to understand
- No infrastructure changes
- 67% faster deployments
- Low cost (same as current)

### For High-Velocity Teams: ECS Fargate (Strategy 4)

**Setup**: Requires CloudFormation changes  
**Deployments**: 1-2 minutes  
**Best for**: Teams deploying 5+ times per day

---

## Deployment Time Comparison

| Strategy | First Deploy | Subsequent | Rebuild Base | Cost Impact |
|----------|-------------|------------|--------------|-------------|
| **Current** | 15 min | 15 min | N/A | $0 |
| **Multi-stage** | 15 min | **3-5 min** | 15 min (monthly) | $0 |
| **+ GLiNER pre-download** | 15 min | **3 min** | 15 min (monthly) | $0 |
| **ECS Fargate** | 5 min | **1-2 min** | N/A | +$15/mo |
| **+ EFS cache** | 5 min | **2-3 min** | N/A | +$10/mo |

---

## Quick Start: Get 3-Minute Deployments Now

```bash
cd aws
source .env

# 1. Build base image once (15 min - grab coffee ☕)
./build-base-image.sh

# 2. From now on, deploy code in 3-5 min
source .env && ./update-fast.sh

# 3. Monitor
./monitor-deployment.sh
```

---

## Migration Path

1. **Week 1**: Build base image, test with `update-fast.sh`
2. **Week 2**: Enable GLiNER pre-download in Dockerfile.base
3. **Week 3**: (Optional) Reduce warmup time to 180s
4. **Month 2+**: (Optional) Consider ECS if deploying frequently

---

## Troubleshooting

### Base image build fails

```bash
# Check Docker has enough memory (8GB recommended)
docker system info | grep Memory

# Clean up old images
docker system prune -a
```

### App image can't find base image

```bash
# Pull base from ECR
source .env
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
docker pull $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/rampart-backend-base:latest
```

### Deployment still slow

```bash
# Verify using app Dockerfile, not main Dockerfile
cd backend
grep "FROM.*base" Dockerfile.app  # Should show base image

# Check instance warmup setting
grep InstanceWarmup ../aws/update-fast.sh  # Should be 180
```

---

## Summary

**Best strategy for you**: Multi-stage Docker build  
**Time investment**: 15 minutes one-time setup  
**Ongoing deployments**: 3-5 minutes (vs 10-15 min)  
**Cost**: $0 additional  
**Frequency of base rebuild**: Once per month  

Deploy faster, iterate quicker! 🚀
