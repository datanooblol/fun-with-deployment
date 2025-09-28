# Data Science Deployment Tutorial

A comprehensive guide for containerized ML deployment using AWS services with proper CI/CD practices.

## 🎯 What You'll Learn

- **Containerized ML Pipelines**: Package your DS code in Docker containers
- **AWS Native Deployment**: Use ECS, Step Functions, EventBridge for orchestration
- **Multi-Account Strategy**: Separate dev/prod environments with shared model artifacts
- **CI/CD Best Practices**: Automated deployment with CodeCommit, CodeBuild, CodePipeline
- **Parameter Management**: Use Parameter Store and Secrets Manager for configuration

## 📁 Repository Structure

```
fun-with-deployment/
├── container_solution/
│   └── preprocessing/          # ML container example
├── infrastructure/             # CDK infrastructure code
├── docs/                      # Tutorial documentation
└── scripts/                   # Utility scripts
```

## 🚀 Quick Start

1. **[Setup Guide](docs/01-SETUP.md)** - Initial AWS account and tool setup
2. **[Container Development](docs/02-CONTAINER.md)** - Build your ML container
3. **[Infrastructure Deployment](docs/03-INFRASTRUCTURE.md)** - Deploy AWS resources
4. **[CI/CD Pipeline](docs/04-CICD.md)** - Automated deployment setup
5. **[Multi-Account Strategy](docs/05-MULTI-ACCOUNT.md)** - Production deployment

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   EventBridge   │───▶│  Step Functions  │───▶│   ECS Fargate   │
│ (15th monthly)  │    │   (Orchestrate)  │    │  (ML Container) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ Parameter Store │    │   S3 Buckets    │
                       │ (Configuration) │    │ (Data & Models) │
                       └─────────────────┘    └─────────────────┘
```

## 💡 Key Features

- **Serverless Orchestration**: No servers to manage
- **Flexible Container Execution**: Custom scripts and packages
- **Cross-Account Model Sharing**: Dev models used in production
- **Automated Scheduling**: Monthly batch processing
- **Comprehensive Monitoring**: CloudWatch logs and metrics

## 🎓 Learning Path

Follow the numbered guides in the `docs/` folder for a step-by-step tutorial that will take you from zero to a production-ready ML deployment pipeline.
