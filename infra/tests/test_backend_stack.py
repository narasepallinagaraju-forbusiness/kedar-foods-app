"""CDK assertions for the read-only backend stack."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from backend_stack import BackendStack


def _stack(
    *,
    env_name: str = "prod",
    cloudfront_domain_name: str = "d123example.cloudfront.net",
    custom_domain_name: str | None = None,
) -> BackendStack:
    app = App()
    return BackendStack(
        app,
        f"kedar-foods-app-{env_name}-backend",
        env_name=env_name,
        cloudfront_domain_name=cloudfront_domain_name,
        custom_domain_name=custom_domain_name,
        env=Environment(account="123456789012", region="ap-south-1"),
        termination_protection=env_name == "prod",
    )


def _template(stack: BackendStack) -> Template:
    return Template.from_stack(stack)


def test_tables_have_fixed_names_pitr_retain_and_expected_gsi() -> None:
    template = _template(_stack())
    tables = template.find_resources("AWS::DynamoDB::Table")
    assert len(tables) == 2
    tables_by_name = {
        resource["Properties"]["TableName"]: resource
        for resource in tables.values()
    }
    products = tables_by_name["kedar-foods-app-prod-products"]
    site_config = tables_by_name["kedar-foods-app-prod-site-config"]
    for table in (products, site_config):
        assert table["Properties"]["BillingMode"] == "PAY_PER_REQUEST"
        assert table["Properties"]["PointInTimeRecoverySpecification"][
            "PointInTimeRecoveryEnabled"
        ]
        assert table["DeletionPolicy"] == "Retain"
        assert table["UpdateReplacePolicy"] == "Retain"
    assert products["Properties"]["KeySchema"] == [
        {"AttributeName": "productId", "KeyType": "HASH"}
    ]
    assert products["Properties"]["GlobalSecondaryIndexes"] == [
        {
            "IndexName": "slug-index",
            "KeySchema": [{"AttributeName": "slug", "KeyType": "HASH"}],
            "Projection": {"ProjectionType": "ALL"},
        }
    ]
    assert site_config["Properties"]["KeySchema"] == [
        {"AttributeName": "configKey", "KeyType": "HASH"}
    ]
    assert products["Properties"]["DeletionProtectionEnabled"] is True
    assert site_config["Properties"]["DeletionProtectionEnabled"] is True


def test_dev_tables_disable_deletion_protection() -> None:
    template = _template(_stack(env_name="dev"))
    for table in template.find_resources("AWS::DynamoDB::Table").values():
        assert table["Properties"]["DeletionProtectionEnabled"] is False


def test_http_api_routes_cors_and_default_throttling() -> None:
    template = _template(_stack(custom_domain_name="shop.example.com"))
    apis = template.find_resources("AWS::ApiGatewayV2::Api")
    assert len(apis) == 1
    api = next(iter(apis.values()))["Properties"]
    cors = api["CorsConfiguration"]
    assert cors["AllowOrigins"] == [
        "https://d123example.cloudfront.net",
        "http://localhost:3000",
        "https://shop.example.com",
    ]
    assert sorted(cors["AllowMethods"]) == ["GET", "OPTIONS"]
    assert cors["AllowCredentials"] is False
    assert cors["AllowHeaders"] == ["Content-Type"]
    assert cors["MaxAge"] == 3600
    assert "*" not in cors["AllowOrigins"]

    routes = {
        resource["Properties"]["RouteKey"]
        for resource in template.find_resources("AWS::ApiGatewayV2::Route").values()
    }
    assert routes == {"GET /products/{slug}", "GET /site-config"}
    stage = next(
        iter(template.find_resources("AWS::ApiGatewayV2::Stage").values())
    )["Properties"]
    assert stage["StageName"] == "$default"
    settings = stage["DefaultRouteSettings"]
    assert settings["ThrottlingRateLimit"] == 20
    assert settings["ThrottlingBurstLimit"] == 40


def test_lambda_runtime_architecture_configuration_and_shared_asset() -> None:
    template = _template(_stack())
    functions = template.find_resources("AWS::Lambda::Function")
    assert len(functions) == 2
    handlers: set[str] = set()
    code_keys: set[str] = set()
    for resource in functions.values():
        properties = resource["Properties"]
        handlers.add(properties["Handler"])
        assert properties["Runtime"] == "python3.12"
        assert properties["Architectures"] == ["arm64"]
        assert properties["MemorySize"] == 512
        assert properties["Timeout"] == 10
        code_keys.add(properties["Code"]["S3Key"])
    assert handlers == {
        "handlers.get_product.handler",
        "handlers.get_site_config.handler",
    }
    assert len(code_keys) == 1

    log_groups = template.find_resources("AWS::Logs::LogGroup")
    assert len(log_groups) == 2
    for log_group in log_groups.values():
        assert log_group["Properties"]["RetentionInDays"] == 30


def test_lambda_asset_excludes_tests_and_python_cache(tmp_path: Path) -> None:
    app = App(outdir=str(tmp_path / "assembly"))
    stack = BackendStack(
        app,
        "kedar-foods-app-prod-backend",
        env_name="prod",
        cloudfront_domain_name="d123example.cloudfront.net",
        env=Environment(account="123456789012", region="ap-south-1"),
    )
    Template.from_stack(stack)
    assembly = app.synth()
    asset_manifest_files = list(Path(assembly.directory).glob("*.assets.json"))
    assert len(asset_manifest_files) == 1
    manifest = cast(dict[str, Any], json.loads(asset_manifest_files[0].read_text()))
    file_assets = {
        key: asset
        for key, asset in manifest["files"].items()
        if asset["source"]["packaging"] == "zip"
    }
    assert len(file_assets) == 1
    source = next(iter(file_assets.values()))["source"]
    asset_archive = Path(assembly.directory) / source["path"]
    assert asset_archive.is_dir()
    names = [
        path.relative_to(asset_archive).as_posix()
        for path in asset_archive.rglob("*")
        if path.is_file()
    ]
    assert not any(name.startswith("tests/") for name in names)
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)


def test_inline_iam_policies_are_exact_read_only_scoped_statements() -> None:
    template = _template(_stack())
    functions = template.find_resources("AWS::Lambda::Function")
    policies = template.find_resources("AWS::IAM::Policy")
    resources = template.to_json()["Resources"]
    products_table_id = next(
        logical_id
        for logical_id, resource in resources.items()
        if resource["Type"] == "AWS::DynamoDB::Table"
        and resource["Properties"]["TableName"] == "kedar-foods-app-prod-products"
    )
    statements_by_function: dict[str, dict[str, Any]] = {}
    for policy in policies.values():
        document = policy["Properties"]["PolicyDocument"]
        statements = document["Statement"]
        role_ref = policy["Properties"]["Roles"][0]["Ref"]
        assert len(statements) == 1
        statements_by_function[role_ref] = statements[0]

    assert len(functions) == 2
    assert len(statements_by_function) == 2
    for function in functions.values():
        props = function["Properties"]
        role_ref = props["Role"]["Fn::GetAtt"][0]
        statement = statements_by_function[role_ref]
        actions = statement["Action"]
        if isinstance(actions, str):
            actions = [actions]
        assert statement["Effect"] == "Allow"
        assert statement["Resource"] != "*"
        assert actions in (["dynamodb:Query"], ["dynamodb:GetItem"])
        assert not any(
            action in actions
            for action in (
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Scan",
            )
        )
        if props["Handler"] == "handlers.get_product.handler":
            assert actions == ["dynamodb:Query"]
            assert statement["Resource"] == {
                "Fn::Join": [
                    "",
                    [
                        {"Fn::GetAtt": [products_table_id, "Arn"]},
                        "/index/slug-index",
                    ],
                ]
            }
        else:
            assert actions == ["dynamodb:GetItem"]


def test_site_config_policy_scopes_to_site_config_table_arn() -> None:
    template = _template(_stack())
    resources = template.to_json()["Resources"]
    site_table_id = next(
        logical_id
        for logical_id, resource in resources.items()
        if resource["Type"] == "AWS::DynamoDB::Table"
        and resource["Properties"]["TableName"] == "kedar-foods-app-prod-site-config"
    )
    policy = next(
        policy
        for policy in template.find_resources("AWS::IAM::Policy").values()
        if policy["Properties"]["PolicyDocument"]["Statement"][0]["Action"]
        in ("dynamodb:GetItem", ["dynamodb:GetItem"])
    )
    assert policy["Properties"]["PolicyDocument"]["Statement"][0]["Resource"] == {
        "Fn::GetAtt": [site_table_id, "Arn"]
    }
