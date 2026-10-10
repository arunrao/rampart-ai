#!/bin/bash
# Deploy the current git HEAD to production.
#
#   ./update.sh                 build + push both images, then zero-downtime instance refresh
#   ./update.sh --backend-only  only rebuild/push the backend image
#   ./update.sh --frontend-only only rebuild/push the frontend image
#   ./update.sh --no-refresh    push images but do not roll instances
#   ./update.sh --allow-dirty   skip the clean-tree / main-branch guard (local experiments)
#
# Images are tagged with the short git SHA *and* `latest`, so what is running in
# production is always answerable from `git log`. Infra/env changes go through
# `./deploy.sh` (CloudFormation) first; this script only ships code.
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

BUILD_BACKEND=1; BUILD_FRONTEND=1; REFRESH=1; ALLOW_DIRTY=0
for arg in "$@"; do
  case "$arg" in
    --backend-only)  BUILD_FRONTEND=0 ;;
    --frontend-only) BUILD_BACKEND=0 ;;
    --no-refresh)    REFRESH=0 ;;
    --allow-dirty)   ALLOW_DIRTY=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo -e "${RED}Unknown flag: $arg${NC}"; exit 2 ;;
  esac
done

cd "$HERE"
if [ -f .env ]; then set -a; source .env; set +a; fi
STACK_NAME="${STACK_NAME:-rampart-production}"
AWS_REGION="${AWS_REGION:-us-west-2}"
DOMAIN_NAME="${DOMAIN_NAME:-rampart.arunrao.com}"
GITHUB_URL="${NEXT_PUBLIC_GITHUB_URL:-https://github.com/arunrao/rampart-ai}"

# ---------------------------------------------------------------------------
# Guards: deploy only committed code from main unless explicitly overridden
# ---------------------------------------------------------------------------
cd "$ROOT"
SHA="$(git rev-parse --short=7 HEAD)"
BRANCH="$(git branch --show-current)"
if [ "$ALLOW_DIRTY" -eq 0 ]; then
  if [ -n "$(git status --porcelain)" ]; then
    echo -e "${RED}Working tree is dirty. Commit (or stash) first so the image matches a git SHA.${NC}"
    echo "  Override for a local experiment with --allow-dirty (image is tagged ${SHA}-dirty)."
    exit 1
  fi
  if [ "$BRANCH" != "main" ]; then
    echo -e "${RED}On branch '$BRANCH'; production deploys from main.${NC} (--allow-dirty to override)"
    exit 1
  fi
  if ! git merge-base --is-ancestor HEAD "origin/main" 2>/dev/null; then
    echo -e "${YELLOW}HEAD is not on origin/main — push first so the deployed SHA exists remotely.${NC}"
    exit 1
  fi
else
  [ -n "$(git status --porcelain)" ] && SHA="${SHA}-dirty"
fi

for tool in aws docker git; do
  command -v "$tool" >/dev/null || { echo -e "${RED}$tool is required${NC}"; exit 1; }
done
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo -e "${GREEN}Deploying ${SHA} (${BRANCH}) to ${STACK_NAME} in ${AWS_REGION}${NC}"
echo "  backend=${BUILD_BACKEND} frontend=${BUILD_FRONTEND} refresh=${REFRESH}"
echo ""

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
if [ "$BUILD_BACKEND" -eq 1 ]; then
  echo -e "${YELLOW}Building backend image...${NC}"
  docker build --platform linux/amd64 \
    --label "org.opencontainers.image.revision=${SHA}" \
    -t "rampart-backend:${SHA}" -t rampart-backend:latest "$ROOT/backend"
fi
if [ "$BUILD_FRONTEND" -eq 1 ]; then
  echo -e "${YELLOW}Building frontend image...${NC}"
  docker build --platform linux/amd64 \
    --label "org.opencontainers.image.revision=${SHA}" \
    --build-arg NEXT_PUBLIC_API_URL="https://${DOMAIN_NAME}/api/v1" \
    --build-arg NEXT_PUBLIC_GITHUB_URL="$GITHUB_URL" \
    -t "rampart-frontend:${SHA}" -t rampart-frontend:latest "$ROOT/frontend"
fi

# ---------------------------------------------------------------------------
# Push (SHA tag + latest)
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Pushing to ECR...${NC}"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR" >/dev/null
push() {  # push <image>
  for tag in "$SHA" latest; do
    docker tag "$1:${SHA}" "${ECR}/$1:${tag}"
    docker push "${ECR}/$1:${tag}" | tail -1
  done
}
[ "$BUILD_BACKEND" -eq 1 ] && push rampart-backend
[ "$BUILD_FRONTEND" -eq 1 ] && push rampart-frontend

# ---------------------------------------------------------------------------
# Roll instances (new instance comes up, is health-checked, then old is retired)
# ---------------------------------------------------------------------------
if [ "$REFRESH" -eq 0 ]; then
  echo -e "${BLUE}Images pushed; skipping instance refresh (--no-refresh).${NC}"
  exit 0
fi

ASG_NAME="$(aws autoscaling describe-auto-scaling-groups --region "$AWS_REGION" \
  --query "AutoScalingGroups[?contains(AutoScalingGroupName, '${STACK_NAME}')].AutoScalingGroupName" --output text)"
[ -n "$ASG_NAME" ] || { echo -e "${RED}Auto Scaling Group for ${STACK_NAME} not found${NC}"; exit 1; }

IN_PROGRESS="$(aws autoscaling describe-instance-refreshes --auto-scaling-group-name "$ASG_NAME" --region "$AWS_REGION" \
  --query 'InstanceRefreshes[?Status==`InProgress`].InstanceRefreshId' --output text)"
if [ -n "$IN_PROGRESS" ]; then
  echo -e "${YELLOW}Cancelling in-progress refresh ${IN_PROGRESS}...${NC}"
  aws autoscaling cancel-instance-refresh --auto-scaling-group-name "$ASG_NAME" --region "$AWS_REGION" >/dev/null
  for _ in $(seq 1 24); do
    sleep 5
    S="$(aws autoscaling describe-instance-refreshes --auto-scaling-group-name "$ASG_NAME" --region "$AWS_REGION" \
      --instance-refresh-ids "$IN_PROGRESS" --query 'InstanceRefreshes[0].Status' --output text)"
    case "$S" in Cancelled|Failed|Successful) break ;; esac
  done
fi

REFRESH_ID="$(aws autoscaling start-instance-refresh --auto-scaling-group-name "$ASG_NAME" --region "$AWS_REGION" \
  --preferences '{"MinHealthyPercentage":100,"MaxHealthyPercentage":200,"InstanceWarmup":300,"CheckpointPercentages":[100],"CheckpointDelay":60,"SkipMatching":false}' \
  --query InstanceRefreshId --output text)"

echo ""
echo -e "${GREEN}Instance refresh started: ${REFRESH_ID}${NC}  (deploying ${SHA})"
echo "  Watch:  ./monitor-deployment.sh"
echo "  Or:     aws autoscaling describe-instance-refreshes --auto-scaling-group-name $ASG_NAME --region $AWS_REGION --instance-refresh-ids $REFRESH_ID"
echo "  Verify: make smoke  (from the repo root)"
