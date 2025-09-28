# Multi-Account Resource Strategy

## 🏗️ Resource Ownership

### **Dev Account (123456789012)**
```
├── ds-input-dev-123456789012-us-east-1     # Dev input data
├── ds-output-dev-123456789012-us-east-1    # Dev results  
├── ds-artifacts-dev-123456789012-us-east-1 # SHARED models ⭐
├── ECR: ds-preprocessing                    # Dev images
├── ECS Cluster: ds-processing-cluster      # Dev compute
└── Step Functions: ds-preprocessing-pipeline # Dev workflow
```

### **Prod Account (987654321098)**  
```
├── ds-input-prod-987654321098-us-east-1    # Prod input data
├── ds-output-prod-987654321098-us-east-1   # Prod results
├── [NO artifact bucket - uses dev's] ❌   # References dev bucket
├── ECR: ds-preprocessing                   # Prod images  
├── ECS Cluster: ds-processing-cluster     # Prod compute
└── Step Functions: ds-preprocessing-pipeline # Prod workflow
```

## 🔄 Data Flow

### **Development Workflow**
```
Dev Input Bucket → Dev Processing → Dev Output Bucket
                     ↓
                Dev Model Bucket (trained models)
```

### **Production Workflow**  
```
Prod Input Bucket → Prod Processing → Prod Output Bucket
                      ↓
                Dev Model Bucket (cross-account read)
```

## 🔐 Cross-Account Access

### **Dev Bucket Policy** (allows prod to read models)
```json
{
  "Effect": "Allow", 
  "Principal": {"AWS": "arn:aws:iam::987654321098:root"},
  "Action": ["s3:GetObject", "s3:ListBucket"],
  "Resource": [
    "arn:aws:s3:::ds-artifacts-dev-123456789012-us-east-1",
    "arn:aws:s3:::ds-artifacts-dev-123456789012-us-east-1/*"
  ]
}
```

### **Prod Task Role** (can access dev models)
```python
task_role.add_to_policy(iam.PolicyStatement(
    actions=["s3:GetObject", "s3:ListBucket"],
    resources=[
        "arn:aws:s3:::ds-artifacts-dev-123456789012-us-east-1",
        "arn:aws:s3:::ds-artifacts-dev-123456789012-us-east-1/*"
    ]
))
```

## 📋 Parameter Store Values

### **Dev Account Parameters**
```
/ds/preprocessing/input-bucket  = ds-input-dev-123456789012-us-east-1
/ds/preprocessing/output-bucket = ds-output-dev-123456789012-us-east-1  
/ds/preprocessing/artifact-bucket = ds-artifacts-dev-123456789012-us-east-1
```

### **Prod Account Parameters**
```
/ds/preprocessing/input-bucket  = ds-input-prod-987654321098-us-east-1
/ds/preprocessing/output-bucket = ds-output-prod-987654321098-us-east-1
/ds/preprocessing/artifact-bucket = ds-artifacts-dev-123456789012-us-east-1 ⭐
```

## 🚀 Deployment Commands

### **Deploy to Dev**
```bash
cd infrastructure
cdk deploy --app "python app.py" --context environment=dev
```

### **Deploy to Prod** 
```bash
# Assume cross-account role first
aws sts assume-role --role-arn arn:aws:iam::987654321098:role/CrossAccountDeployRole --role-session-name prod-deploy

# Then deploy
cdk deploy --app "python app.py" --context environment=prod
```

## 💡 Key Benefits

✅ **Data Isolation**: Each environment has separate input/output data  
✅ **Model Consistency**: Both environments use same trained models  
✅ **Cost Optimization**: No duplicate model storage  
✅ **Security**: Proper cross-account permissions  
✅ **Flexibility**: Can promote models dev → prod easily

## 🔄 Model Promotion Workflow

1. **Train in Dev**: Save model to `ds-artifacts-dev-123456789012-us-east-1/models/v1.2.3/`
2. **Test in Dev**: Dev pipeline uses new model
3. **Update Prod Parameters**: Change `/ds/preprocessing/model-key` to `models/v1.2.3/model.pkl`  
4. **Deploy Prod**: Prod automatically uses new model from dev bucket