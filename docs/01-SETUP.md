# 01 - Initial Setup Guide

## Prerequisites

### Required Tools
```bash
# Install AWS CLI
aws --version

# Install Docker
docker --version

# Install Node.js (for CDK)
node --version

# Install AWS CDK
npm install -g aws-cdk
cdk --version

# Install Python dependencies
pip install aws-cdk-lib constructs boto3
```

### AWS Account Setup

**You'll need TWO AWS accounts:**
- **Dev Account**: For development and testing (Account ID: 123456789012)
- **Prod Account**: For production workloads (Account ID: 987654321098)

### Configure AWS Profiles

```bash
# Configure dev account profile
aws configure --profile dev
AWS Access Key ID: [DEV_ACCESS_KEY]
AWS Secret Access Key: [DEV_SECRET_KEY]
Default region name: us-east-1
Default output format: json

# Configure prod account profile  
aws configure --profile prod
AWS Access Key ID: [PROD_ACCESS_KEY]
AWS Secret Access Key: [PROD_SECRET_KEY]
Default region name: us-east-1
Default output format: json
```

## Repository Structure

```bash
fun-with-deployment/
├── container_solution/
│   └── preprocessing/          # Your ML container
│       ├── Dockerfile
│       ├── main.py            # Container entry point
│       └── pyproject.toml     # Dependencies
├── infrastructure/             # CDK infrastructure code
│   ├── app.py                 # Main CDK app
│   ├── cicd_app.py           # CI/CD infrastructure
│   └── stacks/               # CDK stack definitions
├── docs/                      # This tutorial
├── scripts/                   # Utility scripts
└── pack.py                   # Package creation utility
```

## Cross-Account IAM Setup

### 1. Create Cross-Account Role in Prod Account

```bash
# Switch to prod account
export AWS_PROFILE=prod

# Create trust policy
cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:root"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create the role
aws iam create-role \
  --role-name CrossAccountDeployRole \
  --assume-role-policy-document file://trust-policy.json

# Attach admin policy (for demo - use least privilege in production)
aws iam attach-role-policy \
  --role-name CrossAccountDeployRole \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

### 2. Test Cross-Account Access

```bash
# From dev account, assume prod role
export AWS_PROFILE=dev

aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/CrossAccountDeployRole \
  --role-session-name test-session
```

## Verify Setup

### Test Docker
```bash
cd container_solution/preprocessing
docker build -t test-container .
echo "Docker build successful!"
```

### Test CDK
```bash
cd infrastructure
pip install -r requirements.txt
cdk list --app "python app.py"
# Should show: DSPipelineStack
```

### Test AWS Access
```bash
# Test dev account
export AWS_PROFILE=dev
aws sts get-caller-identity

# Test prod account
export AWS_PROFILE=prod
aws sts get-caller-identity
```

## Next Steps

1. ✅ **Container Development** → [02-CONTAINER.md](02-CONTAINER.md)
2. **Infrastructure Deployment** → [03-INFRASTRUCTURE.md](03-INFRASTRUCTURE.md)
3. **CI/CD Pipeline** → [04-CICD.md](04-CICD.md)
4. **Multi-Account Strategy** → [05-MULTI-ACCOUNT.md](05-MULTI-ACCOUNT.md)

## Troubleshooting

**CDK Bootstrap Required?**
```bash
# If you get bootstrap errors
cdk bootstrap --profile dev
cdk bootstrap --profile prod
```

**Docker Permission Issues?**
```bash
# On Linux/Mac, add user to docker group
sudo usermod -aG docker $USER
# Then logout and login again
```

**AWS Profile Issues?**
```bash
# List configured profiles
aws configure list-profiles

# Test specific profile
aws sts get-caller-identity --profile dev
```