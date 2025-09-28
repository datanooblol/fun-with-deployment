from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class EnvironmentConfig:
    """Configuration for different environments"""
    account_id: str
    region: str
    environment: str
    
    # Each environment has its own buckets
    input_bucket_suffix: str
    output_bucket_suffix: str
    
    # Shared model artifacts (always from dev)
    model_artifact_account: str
    model_artifact_bucket_suffix: str
    
    # Environment-specific settings
    schedule_enabled: bool
    log_retention_days: int

# Environment configurations
ENVIRONMENTS: Dict[str, EnvironmentConfig] = {
    "dev": EnvironmentConfig(
        account_id="123456789012",  # Dev account
        region="us-east-1",
        environment="dev",
        input_bucket_suffix="dev",
        output_bucket_suffix="dev", 
        model_artifact_account="123456789012",  # Same account
        model_artifact_bucket_suffix="dev",
        schedule_enabled=False,  # No auto-schedule in dev
        log_retention_days=7
    ),
    
    "prod": EnvironmentConfig(
        account_id="987654321098",  # Prod account  
        region="us-east-1",
        environment="prod",
        input_bucket_suffix="prod",
        output_bucket_suffix="prod",
        model_artifact_account="123456789012",  # Dev account!
        model_artifact_bucket_suffix="dev",     # Dev bucket!
        schedule_enabled=True,   # Auto-schedule in prod
        log_retention_days=30
    )
}

def get_config(environment: str) -> EnvironmentConfig:
    """Get configuration for environment"""
    if environment not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment: {environment}")
    return ENVIRONMENTS[environment]