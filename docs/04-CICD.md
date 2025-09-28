# 04 - CI/CD Pipeline Guide

## CI/CD Strategy Overview

### Branch-Based Deployment Strategy
```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│     dev     │    │     test     │    │   production    │
│  (develop)  │───▶│ (auto-deploy │───▶│ (auto-deploy    │
│             │    │  to dev acc) │    │  to prod acc)   │
└─────────────┘    └──────────────┘    └─────────────────┘
      ↓                    ↓                      ↓
  No Action          Deploy to Dev          Deploy to Prod
                    Account (123456)       Account (987654)
```

### Deployment Triggers
| Branch | Action | Target Account | Deployment |
|--------|--------|----------------|------------|
| `dev` | Push | None | No deployment |
| `test` | Push/Merge | Dev Account | Automatic |
| `production` | Push/Merge | Prod Account | Automatic |

## CI/CD Infrastructure

### 1. Deploy CI/CD Stack

```bash
# Switch to dev account (where CI/CD runs)
export AWS_PROFILE=dev

# Deploy CI/CD infrastructure
cd infrastructure
cdk deploy --app "python cicd_app.py"
```

**What gets created:**
- ✅ **CodeCommit Repository**: `ds-pipeline`
- ✅ **CodeBuild Projects**: Build and deploy jobs
- ✅ **CodePipeline**: Automated workflows
- ✅ **S3 Bucket**: Pipeline artifacts storage
- ✅ **IAM Roles**: Cross-account deployment permissions

### 2. Setup Git Repository

```bash
# Clone the CodeCommit repository
git clone https://git-codecommit.us-east-1.amazonaws.com/v1/repos/ds-pipeline
cd ds-pipeline

# Copy your project files
cp -r /path/to/fun-with-deployment/* .

# Create branches
git checkout -b dev
git checkout -b test  
git checkout -b production

# Push all branches
git push origin dev
git push origin test
git push origin production
```

## Pipeline Configuration

### Dev Pipeline (test branch → dev account)

**Buildspec for Dev Deployment:**
```yaml
version: 0.2
phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com
      - pip install -r infrastructure/requirements.txt
  build:
    commands:
      - echo Build started on `date`
      - echo Building Docker image...
      - docker build -t ds-preprocessing container_solution/preprocessing/
      - docker tag ds-preprocessing:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/ds-preprocessing:latest
      - echo Deploying CDK stack...
      - cd infrastructure && cdk deploy --app 'python app.py' --context environment=dev --require-approval never
  post_build:
    commands:
      - echo Build completed on `date`
      - echo Pushing Docker image...
      - docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/ds-preprocessing:latest
```

### Production Pipeline (production branch → prod account)

**Cross-Account Deployment:**
```yaml
version: 0.2
phases:
  pre_build:
    commands:
      - echo Assuming cross-account role for production...
      - aws sts assume-role --role-arn $PROD_ROLE_ARN --role-session-name prod-deployment > /tmp/creds.json
      - export AWS_ACCESS_KEY_ID=$(cat /tmp/creds.json | jq -r '.Credentials.AccessKeyId')
      - export AWS_SECRET_ACCESS_KEY=$(cat /tmp/creds.json | jq -r '.Credentials.SecretAccessKey')
      - export AWS_SESSION_TOKEN=$(cat /tmp/creds.json | jq -r '.Credentials.SessionToken')
      - pip install -r infrastructure/requirements.txt
  build:
    commands:
      - echo Deploying to production account...
      - docker build -t ds-preprocessing container_solution/preprocessing/
      - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $PROD_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com
      - docker tag ds-preprocessing:latest $PROD_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/ds-preprocessing:latest
      - cd infrastructure && cdk deploy --app 'python app.py' --context environment=prod --require-approval never
  post_build:
    commands:
      - docker push $PROD_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/ds-preprocessing:latest
```

## Development Workflow

### 1. Feature Development
```bash
# Work on dev branch (no deployments)
git checkout dev

# Make changes to container or infrastructure
vim container_solution/preprocessing/main.py
vim infrastructure/stacks/ds_pipeline_stack.py

# Commit changes
git add .
git commit -m "Add new preprocessing feature"
git push origin dev

# No deployment happens - safe for experimentation
```

### 2. Testing in Dev Environment
```bash
# Merge to test branch (triggers dev deployment)
git checkout test
git merge dev
git push origin test

# Pipeline automatically:
# 1. Builds Docker image
# 2. Pushes to dev account ECR
# 3. Deploys infrastructure to dev account
# 4. Updates ECS task definition
```

### 3. Production Deployment
```bash
# After testing in dev, promote to production
git checkout production
git merge test
git push origin production

# Pipeline automatically:
# 1. Assumes cross-account role
# 2. Builds Docker image
# 3. Pushes to prod account ECR
# 4. Deploys infrastructure to prod account
```

## Cross-Account Setup

### 1. Create Cross-Account Role in Prod Account

```bash
# Switch to prod account
export AWS_PROFILE=prod

# Create trust policy for dev account
cat > cross-account-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "ds-pipeline-deployment"
        }
      }
    }
  ]
}
EOF

# Create the role
aws iam create-role \
  --role-name CrossAccountDeployRole \
  --assume-role-policy-document file://cross-account-trust-policy.json

# Attach deployment permissions
aws iam attach-role-policy \
  --role-name CrossAccountDeployRole \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

## Pipeline Monitoring

### CodePipeline Dashboard
```bash
# View pipeline status
aws codepipeline get-pipeline-state --name ds-pipeline-dev
aws codepipeline get-pipeline-state --name ds-pipeline-prod

# Get execution history
aws codepipeline list-pipeline-executions --pipeline-name ds-pipeline-dev
```

### CodeBuild Logs
```bash
# View build logs
aws logs tail /aws/codebuild/ds-pipeline-dev --follow
aws logs tail /aws/codebuild/ds-pipeline-prod --follow
```

## Testing CI/CD Pipeline

### 1. Test Dev Pipeline
```bash
# Make a small change
echo "# Test change" >> container_solution/preprocessing/main.py

# Push to test branch
git add .
git commit -m "Test CI/CD pipeline"
git checkout test
git merge dev
git push origin test

# Monitor pipeline
aws codepipeline get-pipeline-state --name ds-pipeline-dev
```

### 2. Verify Deployment
```bash
# Check if new image was pushed
aws ecr describe-images --repository-name ds-preprocessing --region us-east-1

# Test the deployed pipeline
STATE_MACHINE_ARN=$(aws stepfunctions list-state-machines --query 'stateMachines[?name==`ds-preprocessing-pipeline`].stateMachineArn' --output text)
aws stepfunctions start-execution --state-machine-arn $STATE_MACHINE_ARN --name "cicd-test-$(date +%s)"
```

### 3. Test Production Pipeline
```bash
# Promote to production
git checkout production
git merge test
git push origin production

# Monitor cross-account deployment
aws codepipeline get-pipeline-state --name ds-pipeline-prod

# Switch to prod account and verify
export AWS_PROFILE=prod
aws stepfunctions list-state-machines
aws ecs list-clusters
```

## Troubleshooting

### Common Issues

**Pipeline Fails at ECR Push**
```bash
# Check ECR permissions
aws ecr get-repository-policy --repository-name ds-preprocessing

# Verify CodeBuild role has ECR permissions
aws iam list-attached-role-policies --role-name codebuild-ds-pipeline-dev-service-role
```

**Cross-Account Deployment Fails**
```bash
# Test role assumption manually
aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/CrossAccountDeployRole \
  --role-session-name test-session

# Check trust relationship
aws iam get-role --role-name CrossAccountDeployRole --profile prod
```

**CDK Deployment Fails**
```bash
# Check CDK bootstrap status
cdk bootstrap --show-template

# Verify CDK version compatibility
cdk --version
pip show aws-cdk-lib
```

## Next Steps

1. ✅ **Setup Guide** → [01-SETUP.md](01-SETUP.md)
2. ✅ **Container Development** → [02-CONTAINER.md](02-CONTAINER.md)  
3. ✅ **Infrastructure Deployment** → [03-INFRASTRUCTURE.md](03-INFRASTRUCTURE.md)
4. ✅ **CI/CD Pipeline** (You are here)
5. **Multi-Account Strategy** → [05-MULTI-ACCOUNT.md](05-MULTI-ACCOUNT.md)

## Best Practices

**Security:**
- Use least-privilege IAM roles
- Enable CloudTrail for deployment auditing
- Scan container images for vulnerabilities
- Use AWS Secrets Manager for sensitive data

**Reliability:**
- Implement proper error handling
- Set up monitoring and alerting
- Use blue/green deployments for zero downtime
- Maintain rollback procedures

**Efficiency:**
- Cache Docker layers for faster builds
- Use parallel builds where possible
- Optimize CDK synthesis time
- Monitor build costs and optimize resources