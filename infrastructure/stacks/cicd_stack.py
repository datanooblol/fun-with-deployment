from aws_cdk import (
    Stack,
    aws_codecommit as codecommit,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as actions,
    aws_iam as iam,
    aws_s3 as s3,
    RemovalPolicy
)
from constructs import Construct

class CICDStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # CodeCommit Repository
        self.repo = codecommit.Repository(self, "DSRepo",
            repository_name="ds-pipeline",
            description="Data Science Pipeline Repository"
        )

        # S3 Bucket for Pipeline Artifacts
        self.artifacts_bucket = s3.Bucket(self, "PipelineArtifacts",
            bucket_name=f"ds-cicd-artifacts-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Create pipelines for different environments
        self.create_dev_pipeline()
        self.create_prod_pipeline()

    def create_dev_pipeline(self):
        """Pipeline for test branch -> dev account"""
        
        # CodeBuild Project for Dev
        dev_build = codebuild.Project(self, "DevBuild",
            project_name="ds-pipeline-dev",
            source=codebuild.Source.code_commit(
                repository=self.repo,
                branch_or_ref="test"
            ),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True  # Needed for Docker builds
            ),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "pre_build": {
                        "commands": [
                            "echo Logging in to Amazon ECR...",
                            "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com",
                            "pip install -r infrastructure/requirements.txt"
                        ]
                    },
                    "build": {
                        "commands": [
                            "echo Build started on `date`",
                            "echo Building Docker image...",
                            "docker build -t ds-preprocessing container_solution/preprocessing/",
                            "docker tag ds-preprocessing:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/ds-preprocessing:latest",
                            "echo Deploying CDK stack...",
                            "cd infrastructure && cdk deploy --app 'python app.py' --require-approval never"
                        ]
                    },
                    "post_build": {
                        "commands": [
                            "echo Build completed on `date`",
                            "echo Pushing Docker image...",
                            "docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/ds-preprocessing:latest"
                        ]
                    }
                }
            }),
            environment_variables={
                "AWS_DEFAULT_REGION": codebuild.BuildEnvironmentVariable(value=self.region),
                "AWS_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(value=self.account)
            }
        )

        # Grant permissions to CodeBuild
        dev_build.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ecr:*",
                "ecs:*", 
                "s3:*",
                "ssm:*",
                "iam:*",
                "logs:*",
                "events:*",
                "states:*",
                "cloudformation:*"
            ],
            resources=["*"]
        ))

        # Dev Pipeline
        dev_pipeline = codepipeline.Pipeline(self, "DevPipeline",
            pipeline_name="ds-pipeline-dev",
            artifact_bucket=self.artifacts_bucket
        )

        # Source stage
        source_output = codepipeline.Artifact()
        dev_pipeline.add_stage(
            stage_name="Source",
            actions=[
                actions.CodeCommitSourceAction(
                    action_name="Source",
                    repository=self.repo,
                    branch="test",
                    output=source_output
                )
            ]
        )

        # Build stage
        dev_pipeline.add_stage(
            stage_name="BuildAndDeploy",
            actions=[
                actions.CodeBuildAction(
                    action_name="BuildAndDeploy",
                    project=dev_build,
                    input=source_output
                )
            ]
        )

    def create_prod_pipeline(self):
        """Pipeline for production branch -> prod account"""
        
        # CodeBuild Project for Prod (cross-account)
        prod_build = codebuild.Project(self, "ProdBuild",
            project_name="ds-pipeline-prod",
            source=codebuild.Source.code_commit(
                repository=self.repo,
                branch_or_ref="production"
            ),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True
            ),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "pre_build": {
                        "commands": [
                            "echo Assuming cross-account role for production...",
                            "aws sts assume-role --role-arn $PROD_ROLE_ARN --role-session-name prod-deployment > /tmp/creds.json",
                            "export AWS_ACCESS_KEY_ID=$(cat /tmp/creds.json | jq -r '.Credentials.AccessKeyId')",
                            "export AWS_SECRET_ACCESS_KEY=$(cat /tmp/creds.json | jq -r '.Credentials.SecretAccessKey')",
                            "export AWS_SESSION_TOKEN=$(cat /tmp/creds.json | jq -r '.Credentials.SessionToken')",
                            "pip install -r infrastructure/requirements.txt"
                        ]
                    },
                    "build": {
                        "commands": [
                            "echo Deploying to production account...",
                            "docker build -t ds-preprocessing container_solution/preprocessing/",
                            "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $PROD_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com",
                            "docker tag ds-preprocessing:latest $PROD_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/ds-preprocessing:latest",
                            "cd infrastructure && cdk deploy --app 'python app.py' --require-approval never"
                        ]
                    },
                    "post_build": {
                        "commands": [
                            "docker push $PROD_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/ds-preprocessing:latest"
                        ]
                    }
                }
            }),
            environment_variables={
                "PROD_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(value="PROD-ACCOUNT-ID"),
                "PROD_ROLE_ARN": codebuild.BuildEnvironmentVariable(value="arn:aws:iam::PROD-ACCOUNT-ID:role/CrossAccountDeployRole")
            }
        )

        # Production Pipeline
        prod_pipeline = codepipeline.Pipeline(self, "ProdPipeline",
            pipeline_name="ds-pipeline-prod",
            artifact_bucket=self.artifacts_bucket
        )

        source_output_prod = codepipeline.Artifact()
        prod_pipeline.add_stage(
            stage_name="Source",
            actions=[
                actions.CodeCommitSourceAction(
                    action_name="Source",
                    repository=self.repo,
                    branch="production",
                    output=source_output_prod
                )
            ]
        )

        prod_pipeline.add_stage(
            stage_name="DeployToProd",
            actions=[
                actions.CodeBuildAction(
                    action_name="DeployToProd",
                    project=prod_build,
                    input=source_output_prod
                )
            ]
        )