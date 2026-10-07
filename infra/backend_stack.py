"""DynamoDB read tables, Lambda handlers, and the public HTTP API."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_apigatewayv2 as apigatewayv2,
)
from aws_cdk import (
    aws_apigatewayv2_integrations as apigatewayv2_integrations,
)
from aws_cdk import (
    aws_dynamodb as dynamodb,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_logs as logs,
)
from constructs import Construct

if TYPE_CHECKING:
    from aws_cdk import Environment


class BackendStack(Stack):
    """Read-only product and site configuration API stack."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str,
        cloudfront_domain_name: str,
        custom_domain_name: str | None = None,
        env: Environment | None = None,
        termination_protection: bool = False,
    ) -> None:
        super().__init__(
            scope,
            construct_id,
            env=env,
            termination_protection=termination_protection,
        )
        resource_prefix = f"kedar-foods-app-{env_name}"

        products_table = dynamodb.Table(
            self,
            "ProductsTable",
            table_name=f"{resource_prefix}-products",
            partition_key=dynamodb.Attribute(
                name="productId",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            deletion_protection=env_name == "prod",
            removal_policy=RemovalPolicy.RETAIN,
        )
        products_table.add_global_secondary_index(
            index_name="slug-index",
            partition_key=dynamodb.Attribute(
                name="slug",
                type=dynamodb.AttributeType.STRING,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        site_config_table = dynamodb.Table(
            self,
            "SiteConfigTable",
            table_name=f"{resource_prefix}-site-config",
            partition_key=dynamodb.Attribute(
                name="configKey",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            deletion_protection=env_name == "prod",
            removal_policy=RemovalPolicy.RETAIN,
        )

        api_directory = Path(__file__).resolve().parent.parent / "api"
        lambda_code = lambda_.Code.from_asset(
            str(api_directory),
            exclude=[
                "tests",
                "tests/**",
                "**/tests/**",
                "**/__pycache__",
                "**/__pycache__/**",
                "**/*.pyc",
            ],
        )
        products_function = self._create_read_function(
            construct_id="GetProductFunction",
            function_name=f"{resource_prefix}-get-product",
            handler="handlers.get_product.handler",
            code=lambda_code,
            environment={"PRODUCTS_TABLE_NAME": products_table.table_name},
        )
        site_config_function = self._create_read_function(
            construct_id="GetSiteConfigFunction",
            function_name=f"{resource_prefix}-get-site-config",
            handler="handlers.get_site_config.handler",
            code=lambda_code,
            environment={"SITE_CONFIG_TABLE_NAME": site_config_table.table_name},
        )

        products_index_arn = f"{products_table.table_arn}/index/slug-index"
        products_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Query"],
                resources=[products_index_arn],
            )
        )
        site_config_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem"],
                resources=[site_config_table.table_arn],
            )
        )

        api_origins = [
            f"https://{cloudfront_domain_name}",
            "http://localhost:3000",
        ]
        if custom_domain_name is not None:
            api_origins.append(f"https://{custom_domain_name}")

        http_api = apigatewayv2.HttpApi(
            self,
            "ReadApi",
            api_name=f"{resource_prefix}-read-api",
            create_default_stage=False,
            cors_preflight=apigatewayv2.CorsPreflightOptions(
                allow_origins=api_origins,
                allow_methods=[
                    apigatewayv2.CorsHttpMethod.GET,
                    apigatewayv2.CorsHttpMethod.OPTIONS,
                ],
                allow_headers=["Content-Type"],
                allow_credentials=False,
                max_age=Duration.seconds(3600),
            ),
        )
        http_api.add_routes(
            path="/products/{slug}",
            methods=[apigatewayv2.HttpMethod.GET],
            integration=apigatewayv2_integrations.HttpLambdaIntegration(
                "GetProductIntegration",
                products_function,
            ),
        )
        http_api.add_routes(
            path="/site-config",
            methods=[apigatewayv2.HttpMethod.GET],
            integration=apigatewayv2_integrations.HttpLambdaIntegration(
                "GetSiteConfigIntegration",
                site_config_function,
            ),
        )
        apigatewayv2.HttpStage(
            self,
            "DefaultStage",
            http_api=http_api,
            stage_name="$default",
            auto_deploy=True,
            throttle=apigatewayv2.ThrottleSettings(
                rate_limit=20,
                burst_limit=40,
            ),
        )

        CfnOutput(self, "ApiUrl", value=http_api.api_endpoint)
        CfnOutput(self, "ProductsTableName", value=products_table.table_name)
        CfnOutput(self, "SiteConfigTableName", value=site_config_table.table_name)

    def _create_read_function(
        self,
        *,
        construct_id: str,
        function_name: str,
        handler: str,
        code: lambda_.Code,
        environment: dict[str, str],
    ) -> lambda_.Function:
        log_group = logs.LogGroup(
            self,
            f"{construct_id}LogGroup",
            log_group_name=f"/aws/lambda/{function_name}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )
        return lambda_.Function(
            self,
            construct_id,
            function_name=function_name,
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            memory_size=512,
            timeout=Duration.seconds(10),
            code=code,
            handler=handler,
            environment=environment,
            log_group=log_group,
        )
