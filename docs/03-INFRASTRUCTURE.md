# 03 - Infrastructure Deployment Guide

## Infrastructure Overview

### What Gets Created
```
📦 S3 Buckets
├── ds-input-{env}-{account}-{region}     # Input data
├── ds-output-{env}-{account}-{region}    # Processed results  
└── ds-artifacts-{env}-{account}-{region} # Models & scripts

🐳 Container Infrastructure  
├── ECR Repository: ds-preprocessing      # Docker images
├── ECS Cluster: ds-processing-cluster   # Container runtime
└── ECS Task Definition                   # Container blueprint

⚙️ Orchestration
├── Step Functions: ds-preprocessing-pipeline # Workflow
├── EventBridge Rule: Monthly trigger         # Scheduler
└── CloudWatch Logs: /ecs/ds-preprocessing   # Monitoring

🔐 Configuration
├── Parameter Store: /ds/preprocessing/*     # Configuration
└── IAM Roles: ECS task permissions         # Security
```

## Parameter Store Structure

### Required Parameters
```
/ds/preprocessing/input-bucket    → ds-input-dev-123456-us-east-1
/ds/preprocessing/output-bucket   → ds-output-dev-123456-us-east-1  
/ds/preprocessing/artifact-bucket → ds-artifacts-dev-123456-us-east-1
/ds/preprocessing/input-key       → raw/monthly_data.csv
/ds/preprocessing/model-key       → models/preprocessing_model.pkl
```

### Optional Parameters
```
/ds/preprocessing/script-key      → scripts/custom_preprocessing.py
/ds/preprocessing/package-key     → packages/custom_package.tar.gz
```

## Deployment Steps

### 1. Deploy Infrastructure (Dev Account)

```bash
# Switch to dev account
export AWS_PROFILE=dev

# Navigate to infrastructure
cd infrastructure

# Install dependencies
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy the stack
cdk deploy --app "python app.py" --context environment=dev
```

**What happens:**
- ✅ Creates all AWS resources
- ✅ Sets up Parameter Store values
- ✅ Creates empty ECR repository
- ✅ Configures IAM permissions

### 2. Build and Push Container Image

```bash
# Get ECR login command
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# Build container
cd ../container_solution/preprocessing
docker build -t ds-preprocessing .

# Tag for ECR
docker tag ds-preprocessing:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/ds-preprocessing:latest

# Push to ECR
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/ds-preprocessing:latest
```

### 3. Upload Sample Data and Models

```bash
# Create sample data
echo "id,value,category" > sample_data.csv
echo "1,100,A" >> sample_data.csv
echo "2,200,B" >> sample_data.csv

# Upload to input bucket
aws s3 cp sample_data.csv s3://ds-input-dev-123456789012-us-east-1/raw/monthly_data.csv

# Create dummy model (in real scenario, this would be your trained model)
echo "dummy model content" > model.pkl
aws s3 cp model.pkl s3://ds-artifacts-dev-123456789012-us-east-1/models/preprocessing_model.pkl
```

## Testing the Pipeline

### Manual Execution
```bash
# Get Step Functions ARN
STATE_MACHINE_ARN=$(aws stepfunctions list-state-machines --query 'stateMachines[?name==`ds-preprocessing-pipeline`].stateMachineArn' --output text)

# Start execution
aws stepfunctions start-execution \
  --state-machine-arn $STATE_MACHINE_ARN \
  --name "test-run-$(date +%s)" \
  --input '{}'

# Monitor execution
aws stepfunctions describe-execution --execution-arn <execution-arn>
```

### Check Logs
```bash
# View container logs
aws logs tail /ecs/ds-preprocessing-dev --follow

# Check Step Functions execution history
aws stepfunctions get-execution-history --execution-arn <execution-arn>
```

### Verify Results
```bash
# Check if output was created
aws s3 ls s3://ds-output-dev-123456789012-us-east-1/processed/

# Download and inspect results
aws s3 cp s3://ds-output-dev-123456789012-us-east-1/processed/data.csv ./output.csv
cat output.csv
```

## Infrastructure Components Deep Dive

### ECS Task Definition
```python
# Task Role - gives container AWS permissions
task_role = iam.Role(self, "TaskRole",
    assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
    managed_policies=[
        iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMReadOnlyAccess")
    ]
)

# Grant S3 permissions
self.input_bucket.grant_read(task_role)
self.output_bucket.grant_write(task_role)
self.artifact_bucket.grant_read(task_role)

# Task Definition - container blueprint
task_def = ecs.FargateTaskDefinition(self, "PreprocessingTask",
    memory_limit_mib=4096,  # 4GB RAM
    cpu=2048,               # 2 vCPUs
    task_role=task_role
)
```

**Key Points:**
- **Fargate**: Serverless containers (no EC2 management)
- **Task Role**: Automatic AWS credentials injection
- **Resource Limits**: Right-sized for ML workloads

### Step Functions Workflow
```python
# ECS Run Task - executes container
run_preprocessing = tasks.EcsRunTask(self, "RunPreprocessing",
    integration_pattern=sfn.IntegrationPattern.RUN_JOB,  # Wait for completion
    cluster=self.cluster,
    task_definition=self.task_definition,
    launch_target=tasks.EcsFargateLaunchTarget()
)

# Error handling
definition = run_preprocessing.add_catch(failure).next(success)
```

**Benefits:**
- **Visual Workflow**: See execution in AWS Console
- **Error Handling**: Automatic retries and notifications
- **Integration**: Easy to add more steps (validation, notifications)

### EventBridge Scheduling
```python
# Monthly trigger - 15th at 9 AM UTC
rule = events.Rule(self, "MonthlySchedule",
    schedule=events.Schedule.cron(
        minute="0",
        hour="9", 
        day="15",
        month="*",
        year="*"
    )
)

rule.add_target(targets.SfnStateMachine(self.state_machine))
```

## Troubleshooting

### Common Issues

**ECR Push Fails**
```bash
# Re-authenticate with ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
```

**Task Fails to Start**
```bash
# Check ECS service events
aws ecs describe-services --cluster ds-processing-cluster --services ds-preprocessing

# Check task definition
aws ecs describe-task-definition --task-definition ds-preprocessing
```

**Parameter Store Access Denied**
```bash
# Verify IAM permissions
aws iam get-role-policy --role-name DSPipelineStack-TaskRole* --policy-name *
```

**Step Functions Execution Fails**
```bash
# Get detailed error information
aws stepfunctions describe-execution --execution-arn <arn>
aws stepfunctions get-execution-history --execution-arn <arn>
```

## Next Steps

1. ✅ **Setup Guide** → [01-SETUP.md](01-SETUP.md)
2. ✅ **Container Development** → [02-CONTAINER.md](02-CONTAINER.md)  
3. ✅ **Infrastructure Deployment** (You are here)
4. **CI/CD Pipeline** → [04-CICD.md](04-CICD.md)
5. **Multi-Account Strategy** → [05-MULTI-ACCOUNT.md](05-MULTI-ACCOUNT.md)

## Best Practices

**Resource Naming:**
- Use consistent naming conventions
- Include environment and account in names
- Make resources easily identifiable

**Security:**
- Use least-privilege IAM roles
- Enable CloudTrail for audit logging
- Encrypt S3 buckets and EBS volumes

**Cost Optimization:**
- Use appropriate Fargate sizing
- Set S3 lifecycle policies
- Monitor CloudWatch costs

**Reliability:**
- Set up proper error handling
- Configure retry policies
- Monitor key metrics and set alarms