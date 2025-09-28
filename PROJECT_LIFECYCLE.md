# Data Science Pipeline - Project Lifecycle

## 🚀 Complete Development Flow

### **Phase 1: Initial Setup**
```bash
# 1. Create AWS accounts (dev, prod)
# 2. Set up cross-account roles
# 3. Deploy CI/CD infrastructure
cd infrastructure
cdk deploy CICDStack --app "python cicd_app.py"
```

### **Phase 2: Infrastructure First**
```bash
# Deploy base infrastructure to dev account
git checkout test
git push origin test  # Triggers dev pipeline

# What gets created:
# ✅ ECR Repository (empty)
# ✅ S3 Buckets
# ✅ Parameter Store
# ✅ ECS Cluster
# ✅ Step Functions
# ✅ EventBridge Rules
```

### **Phase 3: Container Development**
```bash
# Work on your container locally
cd container_solution/preprocessing/

# Test locally
docker build -t ds-preprocessing .
docker run ds-preprocessing

# Iterate until satisfied
# - Fix bugs
# - Add features
# - Test with mock data
```

### **Phase 4: Integration Testing**
```bash
# Push to test branch (triggers dev deployment)
git add .
git commit -m "Add preprocessing logic"
git push origin test

# CI/CD automatically:
# 1. Builds Docker image
# 2. Pushes to ECR
# 3. Updates ECS task definition
# 4. Deploys infrastructure changes
```

### **Phase 5: Production Deployment**
```bash
# Merge to production branch
git checkout production
git merge test
git push origin production

# CI/CD automatically:
# 1. Assumes cross-account role
# 2. Deploys to production account
# 3. Uses dev artifacts (cross-account S3 access)
```

---

## 🔄 CI/CD Branch Strategy

| Branch | Trigger | Target | Action |
|--------|---------|--------|--------|
| `dev` | Push | None | No deployment |
| `test` | Push/Merge | Dev Account | Deploy + Test |
| `production` | Push/Merge | Prod Account | Production Deploy |

---

## 🏗️ Infrastructure Evolution

### **Iteration 1: Basic Pipeline**
- Container + Step Functions
- Manual testing

### **Iteration 2: Add Monitoring**
```python
# Add to ds_pipeline_stack.py
cloudwatch.Alarm(self, "ProcessingFailures",
    metric=self.state_machine.metric_failed(),
    threshold=1
)
```

### **Iteration 3: Add Real-time API**
```bash
# Create new container
mkdir container_solution/api/
# Add FastAPI container
# Update stack with ALB + ECS Service
```

### **Iteration 4: Multi-model Support**
```python
# Update Parameter Store
ssm.StringParameter(self, "ModelVersionParam",
    parameter_name="/ds/preprocessing/model-version",
    string_value="v2.1.0"
)
```

---

## 🔧 Development Best Practices

### **Local Development**
```bash
# 1. Test container locally first
docker build -t test .
docker run -e AWS_PROFILE=dev test

# 2. Use AWS CLI for testing
aws stepfunctions start-execution --state-machine-arn arn:aws:states:...

# 3. Check logs
aws logs tail /ecs/ds-preprocessing --follow
```

### **Environment Management**
```bash
# Different parameter values per environment
/ds/preprocessing/input-bucket
  - dev: ds-input-dev-123456-us-east-1
  - prod: ds-input-prod-789012-us-east-1

# Cross-account model sharing
/ds/preprocessing/artifact-bucket
  - dev: ds-artifacts-dev-123456-us-east-1  
  - prod: ds-artifacts-dev-123456-us-east-1  # Same bucket!
```

### **Rollback Strategy**
```bash
# Tag images for rollback
docker tag ds-preprocessing:latest ds-preprocessing:v1.2.3

# Update task definition to specific version
image=ecs.ContainerImage.from_ecr_repository(self.ecr_repo, "v1.2.3")
```

---

## 📋 Deployment Checklist

### **Before First Deployment**
- [ ] AWS accounts set up (dev, prod)
- [ ] Cross-account IAM roles configured
- [ ] CodeCommit repository created
- [ ] CI/CD stack deployed

### **Before Each Release**
- [ ] Container tested locally
- [ ] Unit tests pass
- [ ] Integration tests in dev
- [ ] Performance benchmarks met
- [ ] Security scan passed

### **Production Deployment**
- [ ] Dev environment validated
- [ ] Rollback plan ready
- [ ] Monitoring alerts configured
- [ ] Team notified
- [ ] Documentation updated