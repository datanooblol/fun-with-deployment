from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_logs as logs,
    Duration,
    RemovalPolicy
)
from constructs import Construct
from .environment_config import get_config

class DSPipelineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, environment: str = "dev", **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get environment configuration
        self.config = get_config(environment)
        self.environment = environment

        # S3 Buckets - Each environment has its own
        self.input_bucket = s3.Bucket(self, "InputBucket",
            bucket_name=f"ds-input-{self.config.input_bucket_suffix}-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )
        
        self.output_bucket = s3.Bucket(self, "OutputBucket", 
            bucket_name=f"ds-output-{self.config.output_bucket_suffix}-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )
        
        # Model artifacts - only create in dev, reference in prod
        if self.environment == "dev":
            self.artifact_bucket = s3.Bucket(self, "ArtifactBucket",
                bucket_name=f"ds-artifacts-{self.config.model_artifact_bucket_suffix}-{self.account}-{self.region}",
                removal_policy=RemovalPolicy.DESTROY,
                auto_delete_objects=True
            )
            # Grant cross-account access to prod
            self.artifact_bucket.add_to_resource_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.AccountPrincipal("987654321098")],  # Prod account
                actions=["s3:GetObject", "s3:ListBucket"],
                resources=[
                    self.artifact_bucket.bucket_arn,
                    f"{self.artifact_bucket.bucket_arn}/*"
                ]
            ))
        else:
            # In prod, reference dev's artifact bucket
            self.artifact_bucket_name = f"ds-artifacts-{self.config.model_artifact_bucket_suffix}-{self.config.model_artifact_account}-{self.region}"

        # ECR Repository
        self.ecr_repo = ecr.Repository(self, "PreprocessingRepo",
            repository_name="ds-preprocessing",
            removal_policy=RemovalPolicy.DESTROY
        )

        # Parameter Store
        self.create_parameters()

        # ECS Cluster
        self.cluster = ecs.Cluster(self, "DSCluster",
            cluster_name="ds-processing-cluster"
        )

        # ECS Task Definition
        self.task_definition = self.create_task_definition()

        # Step Functions
        self.state_machine = self.create_step_function()

        # EventBridge Rule (15th of every month) - only in prod
        if self.config.schedule_enabled:
            self.create_schedule()

    def create_parameters(self):
        """Create Parameter Store parameters"""
        ssm.StringParameter(self, "InputBucketParam",
            parameter_name="/ds/preprocessing/input-bucket",
            string_value=self.input_bucket.bucket_name
        )
        
        ssm.StringParameter(self, "OutputBucketParam",
            parameter_name="/ds/preprocessing/output-bucket", 
            string_value=self.output_bucket.bucket_name
        )
        
        # Artifact bucket parameter - different logic for dev vs prod
        if self.environment == "dev":
            artifact_bucket_name = self.artifact_bucket.bucket_name
        else:
            artifact_bucket_name = self.artifact_bucket_name
            
        ssm.StringParameter(self, "ArtifactBucketParam",
            parameter_name="/ds/preprocessing/artifact-bucket",
            string_value=artifact_bucket_name
        )
        
        ssm.StringParameter(self, "InputKeyParam",
            parameter_name="/ds/preprocessing/input-key",
            string_value="raw/monthly_data.csv"
        )
        
        ssm.StringParameter(self, "ModelKeyParam",
            parameter_name="/ds/preprocessing/model-key",
            string_value="models/preprocessing_model.pkl"
        )
        
        # Optional parameters (can be added later)
        ssm.StringParameter(self, "ScriptKeyParam",
            parameter_name="/ds/preprocessing/script-key",
            string_value="scripts/custom_preprocessing.py"
        )
        
        ssm.StringParameter(self, "PackageKeyParam",
            parameter_name="/ds/preprocessing/package-key", 
            string_value="packages/custom_package.tar.gz"
        )

    def create_task_definition(self):
        """Create ECS Fargate task definition"""
        # Task Role - allows container to access AWS services
        task_role = iam.Role(self, "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMReadOnlyAccess")
            ]
        )
        
        # Grant S3 permissions
        self.input_bucket.grant_read(task_role)
        self.output_bucket.grant_write(task_role)
        
        # Artifact bucket permissions - different for dev vs prod
        if self.environment == "dev":
            self.artifact_bucket.grant_read(task_role)
        else:
            # In prod, grant cross-account access to dev bucket
            task_role.add_to_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject", "s3:ListBucket"],
                resources=[
                    f"arn:aws:s3:::{self.artifact_bucket_name}",
                    f"arn:aws:s3:::{self.artifact_bucket_name}/*"
                ]
            ))

        # Task Definition
        task_def = ecs.FargateTaskDefinition(self, "PreprocessingTask",
            memory_limit_mib=4096,
            cpu=2048,
            task_role=task_role
        )

        # Container Definition
        container = task_def.add_container("preprocessing",
            image=ecs.ContainerImage.from_ecr_repository(self.ecr_repo, "latest"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="preprocessing",
                log_group=logs.LogGroup(self, "PreprocessingLogs",
                    log_group_name=f"/ecs/ds-preprocessing-{self.environment}",
                    removal_policy=RemovalPolicy.DESTROY,
                    retention=logs.RetentionDays(f"DAYS_{self.config.log_retention_days}")
                )
            )
        )

        return task_def

    def create_step_function(self):
        """Create Step Functions state machine"""
        # ECS Run Task
        run_preprocessing = tasks.EcsRunTask(self, "RunPreprocessing",
            integration_pattern=sfn.IntegrationPattern.RUN_JOB,
            cluster=self.cluster,
            task_definition=self.task_definition,
            launch_target=tasks.EcsFargateLaunchTarget(),
            container_overrides=[
                tasks.ContainerOverride(
                    container_definition=self.task_definition.default_container,
                    environment=[
                        tasks.TaskEnvironmentVariable(name="EXECUTION_ID", value=sfn.JsonPath.string_at("$$.Execution.Name"))
                    ]
                )
            ]
        )

        # Success state
        success = sfn.Succeed(self, "ProcessingComplete")

        # Failure state  
        failure = sfn.Fail(self, "ProcessingFailed")

        # Chain states
        definition = run_preprocessing.add_catch(failure).next(success)

        # State Machine
        state_machine = sfn.StateMachine(self, "DSPipeline",
            state_machine_name="ds-preprocessing-pipeline",
            definition=definition,
            timeout=Duration.hours(2)
        )

        return state_machine

    def create_schedule(self):
        """Create EventBridge rule for 15th of every month"""
        rule = events.Rule(self, "MonthlySchedule",
            rule_name="ds-monthly-processing",
            schedule=events.Schedule.cron(
                minute="0",
                hour="9", 
                day="15",
                month="*",
                year="*"
            )
        )

        rule.add_target(targets.SfnStateMachine(self.state_machine))