# Fast deployment

This guide used to describe a separate "base image" workflow (`build-base-image.sh` +
`update-fast.sh`) because the main image took 10–15 minutes to build.

That is no longer necessary:

- `backend/.dockerignore` keeps the build context at ~1 MB (it previously shipped the
  local `venv/`), so a full backend build is ~90 s on an M-series Mac.
- `backend/Dockerfile` pre-downloads the pinned model revisions
  (`backend/models/pinned_revisions.py`) into the image, so there is no cold-start download.

## Deploy

From the repo root:

```bash
make deploy                 # == aws/update.sh: build, push :SHA + :latest, instance refresh
make deploy-backend         # backend image only
make deploy-frontend        # frontend image only
make smoke                  # curl checks against production after the refresh
```

`aws/update.sh` refuses to run from a dirty tree or a branch other than `main`, so the
image in ECR always corresponds to a commit on `origin/main`. Infra/env changes
(CloudFormation parameters, container env vars) go through `aws/deploy.sh` first.

`build-base-image.sh` / `Dockerfile.base` / `Dockerfile.app` are kept for anyone who
wants a two-stage image, but production uses the single `Dockerfile`.
