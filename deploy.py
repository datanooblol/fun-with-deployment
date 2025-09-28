#!/usr/bin/env python3
"""
Deployment script for DS Pipeline
Builds Docker image, pushes to ECR, and deploys CDK stack
"""
import subprocess
import boto3
import json
from pathlib import Path

def get_account_region():
    """Get AWS account and region"""
    sts = boto3.client('sts')
    account = sts.get_caller_identity()['Account']
    region = boto3.Session().region_name or 'us-east-1'
    return account, region

def build_and_push_image():
    """Build and push Docker image to ECR"""
    account, region = get_account_region()
    
    # ECR repository URI
    ecr_uri = f"{account}.dkr.ecr.{region}.amazonaws.com/ds-preprocessing:latest"
    
    print("Building Docker image...")
    subprocess.run([
        "docker", "build", 
        "-t", "ds-preprocessing",
        "-f", "container_solution/preprocessing/Dockerfile",
        "container_solution/preprocessing/"
    ], check=True)
    
    print("Logging into ECR...")
    ecr = boto3.client('ecr', region_name=region)
    token = ecr.get_authorization_token()
    username, password = token['authorizationData'][0]['authorizationToken'].encode('utf-8')
    subprocess.run([
        "docker", "login", "--username", "AWS", "--password-stdin",
        f"{account}.dkr.ecr.{region}.amazonaws.com"
    ], input=password, check=True)
    
    print("Tagging and pushing image...")
    subprocess.run(["docker", "tag", "ds-preprocessing", ecr_uri], check=True)
    subprocess.run(["docker", "push", ecr_uri], check=True)
    
    print(f"Image pushed to {ecr_uri}")

def deploy_infrastructure():
    """Deploy CDK stack"""
    print("Deploying CDK stack...")
    subprocess.run([
        "cdk", "deploy", "--app", "python infrastructure/app.py",
        "--require-approval", "never"
    ], cwd=".", check=True)

if __name__ == "__main__":
    print("Starting deployment...")
    
    # Step 1: Deploy infrastructure (creates ECR repo)
    deploy_infrastructure()
    
    # Step 2: Build and push Docker image
    build_and_push_image()
    
    # Step 3: Update ECS service (if needed)
    print("Deployment complete!")
    print("Pipeline will run on 15th of every month at 9 AM UTC")