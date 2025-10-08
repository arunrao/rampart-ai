# 🔑 Getting AWS Credentials

## Step-by-Step Guide to Get Your AWS Access Keys

### Option 1: Create IAM User (Recommended for Development)

**1. Log into AWS Console**
- Go to https://console.aws.amazon.com/
- Sign in with your AWS account

**2. Navigate to IAM**
- Search for "IAM" in the top search bar
- Click on **IAM** (Identity and Access Management)

**3. Create a New IAM User**
- Click **Users** in the left sidebar
- Click **Create user** button
- Enter username: `rampart-deploy` (or any name you prefer)
- Click **Next**

**4. Set Permissions**
- Select **Attach policies directly**
- Search and select these policies:
  - ✅ `AdministratorAccess` (easiest, full access) **← RECOMMENDED**
  - OR for least privilege, select ALL these:
    - `AmazonEC2FullAccess`
    - `AmazonRDSFullAccess`
    - `AmazonVPCFullAccess`
    - `IAMFullAccess`
    - `CloudFormationFullAccess`
    - `AmazonEC2ContainerRegistryFullAccess` (for ECR/Docker)
    - `SecretsManagerReadWrite`
    - `CloudWatchFullAccess`
    - `ElasticLoadBalancingFullAccess`
    - `AutoScalingFullAccess`
    - `AmazonSSMReadOnlyAccess` (for AMI lookups)
  
  **⚠️ Important:** For simplicity, just use `AdministratorAccess` to avoid permission issues
- Click **Next**
- Click **Create user**

**5. Create Access Keys**
- Click on the user you just created (`rampart-deploy`)
- Go to **Security credentials** tab
- Scroll down to **Access keys** section
- Click **Create access key**
- Select **Command Line Interface (CLI)**
- Check the "I understand" checkbox
- Click **Next**
- (Optional) Add description tag: "Rampart deployment"
- Click **Create access key**

**6. Save Your Credentials** ⚠️ **IMPORTANT**

You'll see:
```
Access key ID: AKIAIOSFODNN7EXAMPLE
Secret access key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

**⚠️ This is your ONLY chance to see the secret access key!**

- Click **Download .csv file** to save them
- Or copy them to a secure location immediately
- Click **Done**

---

### Option 2: Use Root Account Keys (Not Recommended)

If you're using your AWS root account (the email you signed up with):

**⚠️ WARNING:** It's better to create an IAM user (see Option 1) for security.

1. Sign in to AWS Console with your root account
2. Click your account name (top right) → **Security credentials**
3. Expand **Access keys** section
4. Click **Create access key**
5. Download or copy the keys

---

## 🔧 Configure AWS CLI

Once you have your Access Key ID and Secret Access Key:

```bash
# Run this command
aws configure

# You'll be prompted for:
AWS Access Key ID [None]: AKIAIOSFODNN7EXAMPLE
AWS Secret Access Key [None]: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
Default region name [None]: us-east-1
Default output format [None]: json
```

**Default region options:**
- `us-east-1` - US East (N. Virginia) - Most services available
- `us-west-2` - US West (Oregon) - Popular for west coast
- `eu-west-1` - Europe (Ireland)
- `ap-southeast-1` - Asia Pacific (Singapore)

---

## ✅ Verify Configuration

Test that your credentials work:

```bash
# Check your AWS account identity
aws sts get-caller-identity

# Should output:
# {
#     "UserId": "AIDAI...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/rampart-deploy"
# }
```

If you see your account information, you're all set! ✅

---

## 📁 Where Are Credentials Stored?

AWS CLI stores your credentials in:

**Mac/Linux:**
```bash
~/.aws/credentials
~/.aws/config
```

**Windows:**
```
C:\Users\USERNAME\.aws\credentials
C:\Users\USERNAME\.aws\config
```

**Contents of `~/.aws/credentials`:**
```ini
[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

**Contents of `~/.aws/config`:**
```ini
[default]
region = us-east-1
output = json
```

---

## 🔒 Security Best Practices

### ✅ DO:
- Use IAM users instead of root account
- Enable MFA (Multi-Factor Authentication) on IAM user
- Create separate IAM users for different projects
- Rotate access keys regularly (every 90 days)
- Delete unused access keys
- Use IAM roles for production (not access keys)

### ❌ DON'T:
- Share your access keys with anyone
- Commit access keys to git repositories
- Use root account keys for everyday tasks
- Email or message your secret keys
- Store keys in plain text files (except ~/.aws/credentials)

---

## 🔄 Multiple AWS Accounts/Profiles

If you have multiple AWS accounts, use named profiles:

```bash
# Configure a named profile
aws configure --profile rampart-prod

# Use it with setup/deploy
export AWS_PROFILE=rampart-prod
./setup.sh

# Or set it in your .env file
export AWS_PROFILE=rampart-prod
```

---

## 🆘 Troubleshooting

### "Unable to locate credentials"

```bash
# Check if credentials are configured
cat ~/.aws/credentials

# If empty, run:
aws configure
```

### "Access Denied" errors

Your IAM user doesn't have sufficient permissions. Go back to IAM console and add required policies.

### "ExpiredToken" error

Your temporary credentials expired. If using MFA, re-authenticate:

```bash
aws sts get-session-token --serial-number arn:aws:iam::ACCOUNT-ID:mfa/USER-NAME --token-code 123456
```

### Lost/Forgot Secret Access Key

You cannot retrieve it. You must:
1. Go to IAM Console → Users → Your User → Security credentials
2. **Delete** the old access key (mark inactive first to test)
3. **Create** a new access key
4. Run `aws configure` again with new keys

---

## 📚 Additional Resources

- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [AWS CLI Configuration Guide](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- [Managing Access Keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html)

---

## 🎯 Quick Checklist

Before running `./setup.sh`, make sure you have:

- [ ] AWS account created
- [ ] IAM user created with appropriate permissions
- [ ] Access Key ID and Secret Access Key downloaded
- [ ] AWS CLI installed (`aws --version`)
- [ ] AWS CLI configured (`aws configure`)
- [ ] Credentials verified (`aws sts get-caller-identity`)

**Now you're ready to run:**
```bash
cd aws
./setup.sh
```
