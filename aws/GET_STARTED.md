# 🚀 Get Started with AWS Deployment

## What You Need (Checklist)

Before deploying, you need:

### ☐ AWS Account
- Sign up at https://aws.amazon.com/ if you don't have one
- Credit card required (but deployment costs ~$60-70/month)

### ☐ AWS Access Keys
**This is what you asked about!** These are your credentials to use AWS services.

**How to get them:**
1. Go to https://console.aws.amazon.com/iam/
2. Click **Users** → **Create user**
3. Give it a name (e.g., `rampart-deploy`)
4. Attach policy: **AdministratorAccess**
5. Click **Create access key** → **Command Line Interface (CLI)**
6. **Download the CSV file** or copy the keys:
   - Access Key ID (looks like: `AKIAIOSFODNN7EXAMPLE`)
   - Secret Access Key (looks like: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`)

📖 **Detailed guide:** See [AWS_CREDENTIALS_GUIDE.md](AWS_CREDENTIALS_GUIDE.md)

### ☐ AWS CLI Installed

**Mac:**
```bash
brew install awscli
```

**Linux:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

**Windows:**
Download from: https://aws.amazon.com/cli/

### ☐ AWS CLI Configured

```bash
aws configure
```

**You'll be prompted for:**
```
AWS Access Key ID [None]: AKIAIOSFODNN7EXAMPLE       ← From IAM step above
AWS Secret Access Key [None]: wJalrXUtnFEMI/K7MD... ← From IAM step above
Default region name [None]: us-east-1                ← Choose closest to you
Default output format [None]: json                   ← Just press Enter
```

**Verify it works:**
```bash
aws sts get-caller-identity
# Should show your account number and user
```

### ☐ Docker Installed

**Mac:**
Download from: https://www.docker.com/products/docker-desktop

**Linux:**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

**Verify:**
```bash
docker --version
```

### ☐ EC2 Key Pair Created

1. Go to https://console.aws.amazon.com/ec2/
2. Click **Key Pairs** (left sidebar under Network & Security)
3. Click **Create key pair**
4. Name: `rampart-key`
5. Type: RSA
6. Format: `.pem`
7. **Download the file** and save it securely

### ☐ Google OAuth Credentials

1. Go to https://console.cloud.google.com/
2. Create a new project or select existing
3. **APIs & Services** → **Credentials**
4. **Create Credentials** → **OAuth 2.0 Client ID**
5. Application type: **Web application**
6. Name: `Rampart Application`
7. Save the **Client ID** and **Client Secret**
   - (You'll add redirect URIs after deployment)

---

## ✅ Ready? Deploy Now!

Once you have all the checkboxes above:

```bash
cd aws

# Step 1: Run setup wizard
./setup.sh

# Step 2: Load configuration
source .env

# Step 3: Deploy!
./deploy.sh
```

**Deployment takes ~15 minutes**

---

## 💡 Quick Answer to Your Question

> **"Where do I get the AWS CLI keys for the environment variable?"**

**Answer:** You get them from the **IAM Console** in AWS:

1. **Go to:** https://console.aws.amazon.com/iam/
2. **Click:** Users → Create user
3. **Create access keys** for the user
4. **Download/copy** the keys
5. **Run:** `aws configure` and paste them in

**The keys are NOT environment variables** - they're stored by AWS CLI in `~/.aws/credentials` after you run `aws configure`.

The **environment variables** you need for deployment (like `GOOGLE_CLIENT_ID`, `DB_PASSWORD`, etc.) are created by the `setup.sh` script and stored in the `.env` file.

---

## 🆘 Need Help?

- **AWS Access Keys:** See [AWS_CREDENTIALS_GUIDE.md](AWS_CREDENTIALS_GUIDE.md)
- **Full Documentation:** See [README.md](README.md)
- **Quick Start:** See [QUICKSTART.md](QUICKSTART.md)

---

## 📊 Visual Overview

```
┌─────────────────────────────────────────────────┐
│  Prerequisites Setup (One Time)                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  1. AWS Account         ✓                       │
│     └─ Sign up at aws.amazon.com               │
│                                                 │
│  2. AWS Access Keys     ✓                       │
│     └─ IAM Console → Create User → Keys        │
│                                                 │
│  3. AWS CLI             ✓                       │
│     └─ Install → aws configure → Paste keys    │
│                                                 │
│  4. Docker              ✓                       │
│     └─ Install Docker Desktop                  │
│                                                 │
│  5. EC2 Key Pair        ✓                       │
│     └─ EC2 Console → Create key pair           │
│                                                 │
│  6. Google OAuth        ✓                       │
│     └─ Google Console → OAuth credentials      │
│                                                 │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│  Deployment (Run these commands)                │
├─────────────────────────────────────────────────┤
│                                                 │
│  ./setup.sh      ← Configure deployment        │
│  source .env     ← Load configuration          │
│  ./deploy.sh     ← Deploy to AWS               │
│                                                 │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│  Your App is Live! 🎉                           │
│  http://rampart-alb-xxx.amazonaws.com          │
└─────────────────────────────────────────────────┘
```

---

**Ready to get started? See [QUICKSTART.md](QUICKSTART.md) for step-by-step instructions!**
