import boto3
import json
import os
import subprocess
import sys
from pathlib import Path

def initialize_parameters():
    """Get parameters from Parameter Store and Secrets Manager"""
    ssm = boto3.client('ssm')
    
    # Required parameters
    params = {
        'input_bucket': ssm.get_parameter(Name='/ds/preprocessing/input-bucket')['Parameter']['Value'],
        'output_bucket': ssm.get_parameter(Name='/ds/preprocessing/output-bucket')['Parameter']['Value'],
        'artifact_bucket': ssm.get_parameter(Name='/ds/preprocessing/artifact-bucket')['Parameter']['Value'],
        'input_key': ssm.get_parameter(Name='/ds/preprocessing/input-key')['Parameter']['Value'],
        'model_key': ssm.get_parameter(Name='/ds/preprocessing/model-key')['Parameter']['Value']
    }
    
    # Optional parameters
    try:
        params['script_key'] = ssm.get_parameter(Name='/ds/preprocessing/script-key')['Parameter']['Value']
    except ssm.exceptions.ParameterNotFound:
        params['script_key'] = None
        
    try:
        params['package_key'] = ssm.get_parameter(Name='/ds/preprocessing/package-key')['Parameter']['Value']
    except ssm.exceptions.ParameterNotFound:
        params['package_key'] = None
    
    return params

def download_assets(params):
    """Download all required assets from S3"""
    s3 = boto3.client('s3')
    
    # Create working directory
    work_dir = Path('/tmp/work')
    work_dir.mkdir(exist_ok=True)
    
    # Download input data
    # s3.download_file(Bucket, Key, Filename)
    s3.download_file(params['input_bucket'], params['input_key'], '/tmp/work/input_data.csv')
    print(f"Downloaded input data: {params['input_bucket']}/{params['input_key']}")
    
    # Download model artifacts
    # s3.download_file(Bucket, Key, Filename)
    s3.download_file(params['artifact_bucket'], params['model_key'], '/tmp/work/model.pkl')
    print(f"Downloaded model: {params['artifact_bucket']}/{params['model_key']}")
    
    # Download custom script (optional)
    if params.get('script_key'):
        # s3.download_file(Bucket, Key, Filename)
        s3.download_file(params['artifact_bucket'], params['script_key'], '/tmp/work/script.py')
        print(f"Downloaded script: {params['artifact_bucket']}/{params['script_key']}")
    
    # Download custom package folder (optional)
    if params.get('package_key'):
        # Download and extract package folder
        import tarfile
        # s3.download_file(Bucket, Key, Filename)
        s3.download_file(params['artifact_bucket'], params['package_key'], '/tmp/work/package.tar.gz')
        with tarfile.open('/tmp/work/package.tar.gz', 'r:gz') as tar:
            tar.extractall('/tmp/work')
        print(f"Extracted package: {params['artifact_bucket']}/{params['package_key']}")
    
    return work_dir

def start(params):
    """Main processing function"""
    work_dir = download_assets(params)
    
    # Check if custom script exists, otherwise use built-in processing
    custom_script = work_dir / 'script.py'
    if custom_script.exists():
        print("Running custom preprocessing script...")
        # Add work_dir to Python path so script can import package/
        sys.path.insert(0, str(work_dir))
        subprocess.run([sys.executable, str(custom_script)], cwd=work_dir, check=True)
    else:
        print("Running built-in preprocessing...")
        run_builtin_preprocessing(work_dir, params)

def run_builtin_preprocessing(work_dir, params):
    """Built-in preprocessing logic"""
    import pandas as pd
    
    # Load and process data
    df = pd.read_csv(work_dir / 'input_data.csv')
    print(f"Processing {len(df)} rows")
    
    # Your preprocessing logic here
    processed_df = df  # placeholder
    
    # Save results
    output_file = work_dir / 'processed_data.csv'
    processed_df.to_csv(output_file, index=False)
    
    # Upload results
    s3 = boto3.client('s3')
    # s3.upload_file(Filename, Bucket, Key)
    s3.upload_file(str(output_file), params['output_bucket'], 'processed/data.csv')
    print(f"Uploaded results to {params['output_bucket']}/processed/data.csv")

def main():
    """Main entry point"""
    try:
        params = initialize_parameters()
        start(params)
        print("Preprocessing completed successfully.")
    except Exception as e:
        print(f"Error during preprocessing: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()