# 05 - Multi-Account Strategy Guide

## Multi-Account Architecture

### Account Structure
```
┌─────────────────────────────────────┐    ┌─────────────────────────────────────┐
│           DEV ACCOUNT               │    │           PROD ACCOUNT              │
│         (123456789012)              │    │         (987654321098)              │
│                                     │    │                                     │
│  ┌─────────────────────────────┐    │    │  ┌─────────────────────────────┐    │
│  │         S3 Buckets          │    │    │  │         S3 Buckets          │    │
│  │  • ds-input-dev-*           │    │    │  │  • ds-input-prod-*          │    │
│  │  • ds-output-dev-*          │    │    │  │  • ds-output-prod-*         │    │
│  │  • ds-artifacts-dev-* ⭐    │◄───┼────┼──┤    [Uses dev artifacts] ❌  │    │
│  └─────────────────────────────┘    │    │  └─────────────────────────────┘    │
│                                     │    │                                     │
│  ┌─────────────────────────────┐    │    │  ┌─────────────────────────────┐    │
│  │      ECS + Step Functions   │    │    │  │      ECS + Step Functions   │    │
│  │  • Dev pipeline            │    │    │  │  • Prod pipeline           │    │
│  │  • Test data processing    │    │    │  │  • Production workloads    │    │
│  └─────────────────────────────┘    │    │  └─────────────────────────────┘    │
└─────────────────────────────────────┘    └─────────────────────────────────────┘
```

### Resource Ownership Matrix

| Resource Type | Dev Account | Prod Account | Shared |
|---------------|-------------|--------------|--------|
| Input Data Buckets | ✅ Own | ✅ Own | ❌ |
| Output Data Buckets | ✅ Own | ✅ Own | ❌ |
| Model Artifacts | ✅ Own | ❌ Uses Dev | ✅ |
| ECR Repositories | ✅ Own | ✅ Own | ❌ |
| ECS Clusters | ✅ Own | ✅ Own | ❌ |
| Step Functions | ✅ Own | ✅ Own | ❌ |
| Parameter Store | ✅ Own | ✅ Own | ❌ |

## Environment Configuration

### Environment-Specific Deployments

**Deploy to Dev Account:**
```bash
# Switch to dev account
export AWS_PROFILE=dev

# Deploy with dev configuration
cd infrastructure
cdk deploy --app "python app.py" --context environment=dev
```

**Deploy to Prod Account:**
```bash
# Switch to prod account (or use cross-account role)
export AWS_PROFILE=prod

# Deploy with prod configuration
cd infrastructure
cdk deploy --app "python app.py" --context environment=prod
```

### Configuration Differences

```python
# environment_config.py
ENVIRONMENTS = {
    "dev": EnvironmentConfig(
        account_id="123456789012",
        environment="dev",
        input_bucket_suffix="dev",
        output_bucket_suffix="dev",
        model_artifact_account="123456789012",  # Same account
        model_artifact_bucket_suffix="dev",
        schedule_enabled=False,  # No auto-schedule in dev
        log_retention_days=7
    ),
    
    "prod": EnvironmentConfig(
        account_id="987654321098",
        environment="prod",
        input_bucket_suffix="prod",
        output_bucket_suffix="prod",
        model_artifact_account="123456789012",  # Dev account!
        model_artifact_bucket_suffix="dev",     # Dev bucket!
        schedule_enabled=True,   # Auto-schedule in prod
        log_retention_days=30
    )
}
```

## Cross-Account Permissions

### 1. S3 Cross-Account Access

**Dev Account - Artifact Bucket Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowProdAccountAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::987654321098:root"
      },
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::ds-artifacts-dev-123456789012-us-east-1",
        "arn:aws:s3:::ds-artifacts-dev-123456789012-us-east-1/*"
      ]
    }
  ]
}
```

**Prod Account - ECS Task Role:**
```python
# In prod account, task role gets cross-account S3 permissions
task_role.add_to_policy(iam.PolicyStatement(
    effect=iam.Effect.ALLOW,
    actions=["s3:GetObject", "s3:ListBucket"],
    resources=[
        "arn:aws:s3:::ds-artifacts-dev-123456789012-us-east-1",
        "arn:aws:s3:::ds-artifacts-dev-123456789012-us-east-1/*"
    ]
))
```

### 2. Cross-Account Deployment Role

**Create in Prod Account:**
```bash
# Switch to prod account
export AWS_PROFILE=prod

# Create deployment role
aws iam create-role \
  --role-name CrossAccountDeployRole \
  --assume-role-policy-document '{
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
  }'

# Attach deployment permissions
aws iam attach-role-policy \
  --role-name CrossAccountDeployRole \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

**Use from Dev Account:**
```bash
# Assume role for cross-account deployment
aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/CrossAccountDeployRole \
  --role-session-name prod-deployment
```

## Parameter Store Strategy

### Dev Account Parameters
```
/ds/preprocessing/input-bucket    = ds-input-dev-123456789012-us-east-1
/ds/preprocessing/output-bucket   = ds-output-dev-123456789012-us-east-1
/ds/preprocessing/artifact-bucket = ds-artifacts-dev-123456789012-us-east-1
/ds/preprocessing/input-key       = raw/monthly_data.csv
/ds/preprocessing/model-key       = models/preprocessing_model.pkl
```

### Prod Account Parameters
```
/ds/preprocessing/input-bucket    = ds-input-prod-987654321098-us-east-1
/ds/preprocessing/output-bucket   = ds-output-prod-987654321098-us-east-1
/ds/preprocessing/artifact-bucket = ds-artifacts-dev-123456789012-us-east-1 ⭐
/ds/preprocessing/input-key       = raw/monthly_data.csv
/ds/preprocessing/model-key       = models/preprocessing_model.pkl
```

**Key Point:** Prod uses dev's artifact bucket for model consistency!

## Model Promotion Workflow

### 1. Model Development (Dev Account)
```bash
# Train and save model in dev
aws s3 cp trained_model.pkl s3://ds-artifacts-dev-123456789012-us-east-1/models/v1.2.3/model.pkl

# Update dev parameter to test new model
aws ssm put-parameter \
  --name "/ds/preprocessing/model-key" \
  --value "models/v1.2.3/model.pkl" \
  --overwrite

# Test in dev environment
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:123456789012:stateMachine:ds-preprocessing-pipeline \
  --name "test-new-model-$(date +%s)"
```

### 2. Model Validation
```bash
# Run validation tests
python scripts/validate_model.py \
  --model-path s3://ds-artifacts-dev-123456789012-us-east-1/models/v1.2.3/model.pkl \
  --test-data s3://ds-input-dev-123456789012-us-east-1/validation/test_data.csv

# Check performance metrics
aws cloudwatch get-metric-statistics \
  --namespace "DS/Pipeline" \
  --metric-name "ProcessingTime" \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 3600 \
  --statistics Average
```

### 3. Production Promotion
```bash
# Switch to prod account
export AWS_PROFILE=prod

# Update prod parameter to use new model
aws ssm put-parameter \
  --name "/ds/preprocessing/model-key" \
  --value "models/v1.2.3/model.pkl" \
  --overwrite

# Prod pipeline automatically uses new model from dev bucket!
# No need to copy model - cross-account access handles it
```

## Data Flow Patterns

### Development Data Flow
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Dev Input     │───▶│  Dev Pipeline   │───▶│   Dev Output    │
│     Bucket      │    │   (ECS Task)    │    │     Bucket      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Dev Models    │
                       │     Bucket      │
                       └─────────────────┘
```

### Production Data Flow
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Prod Input    │───▶│  Prod Pipeline  │───▶│   Prod Output   │
│     Bucket      │    │   (ECS Task)    │    │     Bucket      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Dev Models    │ ⭐
                       │ (Cross-Account) │
                       └─────────────────┘
```

## Testing Multi-Account Setup

### 1. Test Cross-Account Model Access
```bash
# From prod account, test model download
export AWS_PROFILE=prod

# Create test ECS task
aws ecs run-task \
  --cluster ds-processing-cluster \
  --task-definition ds-preprocessing \
  --launch-type FARGATE \
  --network-configuration 'awsvpcConfiguration={subnets=[subnet-12345],assignPublicIp=ENABLED}'

# Check logs to verify model download
aws logs tail /ecs/ds-preprocessing-prod --follow
```

### 2. Test Parameter Store Isolation
```bash
# Dev parameters
export AWS_PROFILE=dev
aws ssm get-parameter --name "/ds/preprocessing/input-bucket"
# Should return: ds-input-dev-123456789012-us-east-1

# Prod parameters
export AWS_PROFILE=prod
aws ssm get-parameter --name "/ds/preprocessing/input-bucket"
# Should return: ds-input-prod-987654321098-us-east-1
```

### 3. Test End-to-End Pipeline
```bash
# Upload test data to prod input bucket
export AWS_PROFILE=prod
echo "id,value" > test_data.csv
echo "1,100" >> test_data.csv
aws s3 cp test_data.csv s3://ds-input-prod-987654321098-us-east-1/raw/monthly_data.csv

# Run prod pipeline
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:987654321098:stateMachine:ds-preprocessing-pipeline \
  --name "multi-account-test-$(date +%s)"

# Verify results in prod output bucket
aws s3 ls s3://ds-output-prod-987654321098-us-east-1/processed/
```

## Troubleshooting Multi-Account Issues

### Cross-Account Access Denied
```bash
# Check bucket policy
aws s3api get-bucket-policy --bucket ds-artifacts-dev-123456789012-us-east-1

# Verify cross-account trust
aws iam get-role --role-name CrossAccountDeployRole --profile prod

# Test assume role
aws sts assume-role \
  --role-arn arn:aws:iam::987654321098:role/CrossAccountDeployRole \
  --role-session-name test
```

### Parameter Store Sync Issues
```bash
# Compare parameters between accounts
echo "Dev parameters:"
aws ssm get-parameters-by-path --path "/ds/preprocessing" --profile dev

echo "Prod parameters:"
aws ssm get-parameters-by-path --path "/ds/preprocessing" --profile prod
```

### Model Version Mismatches
```bash
# Check which model version each environment is using
echo "Dev model:"
aws ssm get-parameter --name "/ds/preprocessing/model-key" --profile dev

echo "Prod model:"
aws ssm get-parameter --name "/ds/preprocessing/model-key" --profile prod

# List available models in dev bucket
aws s3 ls s3://ds-artifacts-dev-123456789012-us-east-1/models/ --recursive --profile dev
```

## Best Practices

### Security
- ✅ Use least-privilege cross-account roles
- ✅ Enable CloudTrail in both accounts
- ✅ Regularly rotate access keys
- ✅ Monitor cross-account access patterns

### Cost Optimization
- ✅ Share expensive resources (models, large datasets)
- ✅ Use different instance sizes per environment
- ✅ Implement lifecycle policies for dev data
- ✅ Monitor cross-region data transfer costs

### Operational Excellence
- ✅ Maintain environment parity where possible
- ✅ Automate cross-account deployments
- ✅ Document account-specific configurations
- ✅ Test disaster recovery procedures

### Reliability
- ✅ Implement proper error handling for cross-account calls
- ✅ Set up monitoring and alerting for both accounts
- ✅ Plan for account-level failures
- ✅ Maintain backup strategies for shared resources

## Conclusion

You now have a complete multi-account ML deployment strategy that provides:

- **Environment Isolation**: Separate dev/prod with proper boundaries
- **Resource Sharing**: Efficient model artifact sharing
- **Automated Deployment**: CI/CD across accounts
- **Security**: Proper cross-account permissions
- **Monitoring**: Visibility across environments

This setup scales to support multiple teams, models, and use cases while maintaining security and operational excellence!