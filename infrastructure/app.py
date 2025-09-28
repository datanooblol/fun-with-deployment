#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.ds_pipeline_stack import DSPipelineStack

app = cdk.App()

DSPipelineStack(app, "DSPipelineStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1" # change to your preferred region
    )
)

app.synth()