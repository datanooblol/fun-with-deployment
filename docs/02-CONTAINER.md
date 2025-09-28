# 02 - Container Development Guide

## Container Architecture

### Container Purpose
Our container is designed to:
- **Download** data and models from S3
- **Process** data using custom or built-in logic
- **Upload** results back to S3
- **Configure** everything via Parameter Store

### Container Flow
```
1. Read Parameter Store → Get S3 paths and config
2. Download Assets → Data, models, custom scripts
3. Execute Processing → Run custom script or built-in logic
4. Upload Results → Save processed data to S3
```

## Container Structure

```
container_solution/preprocessing/
├── Dockerfile              # Container definition
├── main.py                # Entry point with AWS integration
└── pyproject.toml         # Python dependencies
```

## Deep Dive: main.py

### Parameter Store Integration
```python
def initialize_parameters():
    """Get parameters from Parameter Store"""
    ssm = boto3.client('ssm')
    
    # Required parameters
    params = {
        'input_bucket': ssm.get_parameter(Name='/ds/preprocessing/input-bucket')['Parameter']['Value'],
        'output_bucket': ssm.get_parameter(Name='/ds/preprocessing/output-bucket')['Parameter']['Value'],
        'artifact_bucket': ssm.get_parameter(Name='/ds/preprocessing/artifact-bucket')['Parameter']['Value'],
        'input_key': ssm.get_parameter(Name='/ds/preprocessing/input-key')['Parameter']['Value'],
        'model_key': ssm.get_parameter(Name='/ds/preprocessing/model-key')['Parameter']['Value']
    }
```

**Key Points:**
- ✅ **No hardcoded values** - everything from Parameter Store
- ✅ **Environment agnostic** - same code works in dev/prod
- ✅ **Automatic credentials** - uses ECS task role

### S3 Asset Management
```python
def download_assets(params):
    """Download all required assets from S3"""
    s3 = boto3.client('s3')
    
    # s3.download_file(Bucket, Key, Filename)
    s3.download_file(params['input_bucket'], params['input_key'], '/tmp/work/input_data.csv')
    s3.download_file(params['artifact_bucket'], params['model_key'], '/tmp/work/model.pkl')
```

**S3 Function Signatures:**
- **Download**: `s3.download_file(Bucket, Key, LocalPath)`
- **Upload**: `s3.upload_file(LocalPath, Bucket, Key)`

### Flexible Execution Model
```python
def start(params):
    work_dir = download_assets(params)
    
    # Check if custom script exists
    custom_script = work_dir / 'script.py'
    if custom_script.exists():
        # Run custom script with proper Python path
        sys.path.insert(0, str(work_dir))
        subprocess.run([sys.executable, str(custom_script)], cwd=work_dir, check=True)
    else:
        # Run built-in processing
        run_builtin_preprocessing(work_dir, params)
```

**Execution Options:**
1. **Built-in Processing**: Default pandas-based processing
2. **Custom Script**: Download and run your own `script.py`
3. **Custom Package**: Download, extract, and import custom modules

## Local Development Workflow

### 1. Build and Test Locally
```bash
cd container_solution/preprocessing

# Build the container
docker build -t ds-preprocessing .

# Test with mock environment variables
docker run -e AWS_PROFILE=dev ds-preprocessing
```

### 2. Test with Real AWS
```bash
# Set AWS profile and test
export AWS_PROFILE=dev
docker run -v ~/.aws:/root/.aws ds-preprocessing
```

## Custom Package Development

### Your Project Structure
```
my-ds-project/
├── package/
│   ├── __init__.py
│   ├── preprocessing.py
│   └── models/
│       └── custom_model.py
└── script.py              # Uses: from package.preprocessing import *
```

### Package and Upload
```bash
# Use the pack.py utility
python pack.py

# Or manually:
tar -czf package.tar.gz package/
aws s3 cp package.tar.gz s3://your-artifacts-bucket/packages/
aws s3 cp script.py s3://your-artifacts-bucket/scripts/
```

### Container Execution
1. Downloads `package.tar.gz` and `script.py`
2. Extracts package to `/tmp/work/package/`
3. Adds `/tmp/work` to Python path
4. Runs `script.py` which can import from `package/`

## Dockerfile Optimization

### Current Dockerfile
```dockerfile
FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml .
COPY main.py .

RUN uv sync

CMD [ "uv", "run", "main.py"]
```

### Why This Design?
- ✅ **Fast builds** with `uv` package manager
- ✅ **Minimal dependencies** - only what's needed
- ✅ **Lean image** - Python slim base
- ✅ **Reproducible** - locked dependencies

## Testing Strategies

### Unit Testing
```python
# test_main.py
import pytest
from unittest.mock import patch, MagicMock
from main import initialize_parameters, download_assets

@patch('boto3.client')
def test_initialize_parameters(mock_boto):
    # Mock SSM client
    mock_ssm = MagicMock()
    mock_boto.return_value = mock_ssm
    mock_ssm.get_parameter.return_value = {'Parameter': {'Value': 'test-bucket'}}
    
    params = initialize_parameters()
    assert params['input_bucket'] == 'test-bucket'
```

### Integration Testing
```bash
# Test with real AWS resources
export AWS_PROFILE=dev
python -m pytest tests/ -v
```

### Container Testing
```bash
# Test full container workflow
docker run --rm \
  -v ~/.aws:/root/.aws \
  -e AWS_PROFILE=dev \
  ds-preprocessing
```

## Next Steps

1. ✅ **Container Development** (You are here)
2. **Infrastructure Deployment** → [03-INFRASTRUCTURE.md](03-INFRASTRUCTURE.md)
3. **CI/CD Pipeline** → [04-CICD.md](04-CICD.md)
4. **Multi-Account Strategy** → [05-MULTI-ACCOUNT.md](05-MULTI-ACCOUNT.md)

## Pro Tips

**Debugging Container Issues:**
```bash
# Run container interactively
docker run -it --entrypoint /bin/bash ds-preprocessing

# Check logs in AWS
aws logs tail /ecs/ds-preprocessing-dev --follow
```

**Security Best Practices:**
- Never hardcode credentials
- Use least-privilege IAM roles
- Scan images for vulnerabilities
- Use specific dependency versions