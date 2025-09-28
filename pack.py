import tarfile
import boto3
from pathlib import Path

def create_package(package_dir, output_file):
    """Create tar.gz from package directory"""
    package_path = Path(package_dir)
    if not package_path.exists():
        raise FileNotFoundError(f"Package directory {package_dir} not found")
    
    with tarfile.open(output_file, 'w:gz') as tar:
        tar.add(package_path, arcname=package_path.name)
    
    print(f"Created {output_file} from {package_dir}")
    return output_file

def upload_to_s3(local_file, bucket, key):
    """Upload file to S3"""
    s3 = boto3.client('s3')
    s3.upload_file(local_file, bucket, key)
    print(f"Uploaded {local_file} to s3://{bucket}/{key}")

if __name__ == "__main__":
    # Example usage
    package_tar = create_package("package", "package.tar.gz")
    upload_to_s3("package.tar.gz", "your-bucket", "artifacts/package.tar.gz")
    upload_to_s3("script.py", "your-bucket", "artifacts/script.py")