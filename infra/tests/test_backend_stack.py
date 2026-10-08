"""CDK assertions for the read-only backend stack."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from aws_cdk import App, Environment
from aws_cdk.assertions import Template

from backend_stack import BackendStack

ADMIN_ROUTES = {
    "GET /admin/products",
    "POST /admin/products",
    "POST /admin/products/import",
    "GET /admin/products/{id}",
    "PUT /admin/products/{id}",
    "POST /admin/products/{id}/archive",
    "POST /admin/products/{id}/restore",
    "POST /admin/catalog-index/rebuild",
    "GET /admin/site-config",
    "PUT /admin/site-config/offer",
    "PUT /admin/products/{id}/images/{slot}",
    "POST /admin/products/{id}/images/{slot}/remove",
    "PUT /admin/site-config/offer/image",
    "POST /admin/site-config/offer/image/remove",
}

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
        data_bucket_name="kedar-foods-app-prod-data-media",
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
    assert sorted(cors["AllowMethods"]) == ["GET", "OPTIONS", "POST", "PUT"]
    assert cors["AllowCredentials"] is False
    assert cors["AllowHeaders"] == ["Content-Type", "X-Admin-Key"]
    assert cors["MaxAge"] == 3600
    assert "*" not in cors["AllowOrigins"]

    routes = {
        resource["Properties"]["RouteKey"]
        for resource in template.find_resources("AWS::ApiGatewayV2::Route").values()
    }
    assert routes == {"GET /products/{slug}", "GET /site-config", *ADMIN_ROUTES}
    stage = next(
        iter(template.find_resources("AWS::ApiGatewayV2::Stage").values())
    )["Properties"]
    assert stage["StageName"] == "$default"
    settings = stage["DefaultRouteSettings"]
    assert settings["ThrottlingRateLimit"] == 20
    assert settings["ThrottlingBurstLimit"] == 40
    route_settings = stage["RouteSettings"]
    assert set(route_settings) == set(ADMIN_ROUTES)
    for route_key, value in route_settings.items():
        if route_key == "POST /admin/products/import":
            assert value["ThrottlingRateLimit"] == 1
            assert value["ThrottlingBurstLimit"] == 2
        elif "/image" in route_key:
            assert value["ThrottlingRateLimit"] == 2
            assert value["ThrottlingBurstLimit"] == 5
        else:
            assert value["ThrottlingRateLimit"] == 5
            assert value["ThrottlingBurstLimit"] == 10


def test_every_admin_route_uses_an_admin_lambda_integration() -> None:
    template = _template(_stack())
    functions = template.find_resources("AWS::Lambda::Function")
    handler_by_id = {
        logical_id: resource["Properties"]["Handler"]
        for logical_id, resource in functions.items()
    }
    integrations = template.find_resources("AWS::ApiGatewayV2::Integration")
    handler_by_integration: dict[str, str] = {}
    for logical_id, integration in integrations.items():
        uri = json.dumps(integration["Properties"]["IntegrationUri"])
        for function_id, handler in handler_by_id.items():
            if function_id in uri:
                handler_by_integration[logical_id] = handler
    for route in template.find_resources("AWS::ApiGatewayV2::Route").values():
        key = route["Properties"]["RouteKey"]
        target = json.dumps(route["Properties"]["Target"])
        handler = next(
            h for i, h in handler_by_integration.items() if i in target
        )
        if key in ADMIN_ROUTES:
            assert handler.startswith("handlers.admin_")
            assert "AuthorizationType" not in route["Properties"] or (
                route["Properties"]["AuthorizationType"] == "NONE"
            )
        else:
            assert not handler.startswith("handlers.admin_")


def test_lambda_runtime_architecture_configuration_and_shared_asset() -> None:
    template = _template(_stack())
    functions = template.find_resources("AWS::Lambda::Function")
    assert len(functions) == 5
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
        "handlers.admin_products.handler",
        "handlers.admin_site_config.handler",
        "handlers.admin_images.handler",
    }
    assert len(code_keys) == 1

    log_groups = template.find_resources("AWS::Logs::LogGroup")
    assert len(log_groups) == 5
    for log_group in log_groups.values():
        assert log_group["Properties"]["RetentionInDays"] == 30


def test_lambda_asset_excludes_tests_and_python_cache(tmp_path: Path) -> None:
    app = App(outdir=str(tmp_path / "assembly"))
    stack = BackendStack(
        app,
        "kedar-foods-app-prod-backend",
        env_name="prod",
        cloudfront_domain_name="d123example.cloudfront.net",
        data_bucket_name="kedar-foods-app-prod-data-media",
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
    statements_by_function: dict[str, list[dict[str, Any]]] = {}
    for policy in policies.values():
        document = policy["Properties"]["PolicyDocument"]
        statements = document["Statement"]
        role_ref = policy["Properties"]["Roles"][0]["Ref"]
        statements_by_function[role_ref] = statements

    assert len(functions) == 5
    assert len(statements_by_function) == 5
    for function in functions.values():
        props = function["Properties"]
        if props["Handler"].startswith("handlers.admin_"):
            continue
        role_ref = props["Role"]["Fn::GetAtt"][0]
        assert len(statements_by_function[role_ref]) == 1
        statement = statements_by_function[role_ref][0]
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
        if len(policy["Properties"]["PolicyDocument"]["Statement"]) == 1
        and policy["Properties"]["PolicyDocument"]["Statement"][0]["Action"]
        in ("dynamodb:GetItem", ["dynamodb:GetItem"])
    )
    assert policy["Properties"]["PolicyDocument"]["Statement"][0]["Resource"] == {
        "Fn::GetAtt": [site_table_id, "Arn"]
    }


def _admin_statements(template: Template, handler: str) -> list[dict[str, Any]]:
    functions = template.find_resources("AWS::Lambda::Function")
    role_ref = next(
        resource["Properties"]["Role"]["Fn::GetAtt"][0]
        for resource in functions.values()
        if resource["Properties"]["Handler"] == handler
    )
    statements: list[dict[str, Any]] = []
    for policy in template.find_resources("AWS::IAM::Policy").values():
        if policy["Properties"]["Roles"][0]["Ref"] == role_ref:
            statements.extend(policy["Properties"]["PolicyDocument"]["Statement"])
    return statements


def _actions(statements: list[dict[str, Any]]) -> set[str]:
    actions: set[str] = set()
    for statement in statements:
        value = statement["Action"]
        actions.update([value] if isinstance(value, str) else value)
    return actions


def test_admin_functions_have_scoped_permissions_and_no_wildcards() -> None:
    template = _template(_stack())
    products = _admin_statements(template, "handlers.admin_products.handler")
    site_config = _admin_statements(template, "handlers.admin_site_config.handler")

    assert _actions(products) == {
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Scan",
        "dynamodb:Query",
        "s3:PutObject",
        "ssm:GetParameter",
    }
    assert _actions(site_config) == {
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "ssm:GetParameter",
    }
    for statement in [*products, *site_config]:
        assert statement["Effect"] == "Allow"
        assert statement["Resource"] != "*"
        assert "*" not in json.dumps(statement["Action"])
    for action in ("dynamodb:DeleteItem", "s3:DeleteObject", "s3:GetObject"):
        assert action not in _actions(products) | _actions(site_config)


def test_admin_s3_write_is_limited_to_the_index_object() -> None:
    template = _template(_stack())
    statements = _admin_statements(template, "handlers.admin_products.handler")
    s3_statements = [
        s for s in statements if "s3:PutObject" in _actions([s])
    ]

    assert len(s3_statements) == 1
    assert s3_statements[0]["Action"] == "s3:PutObject"
    assert json.dumps(s3_statements[0]["Resource"]).endswith(
        'kedar-foods-app-prod-data-media/data/catalog-index.json"]]}'
    )


def test_admin_image_function_can_only_write_picture_and_index_keys() -> None:
    template = _template(_stack())
    statements = _admin_statements(template, "handlers.admin_images.handler")

    assert _actions(statements) == {
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:Scan",
        "s3:PutObject",
        "ssm:GetParameter",
    }
    s3_statements = [s for s in statements if "s3:PutObject" in _actions([s])]
    assert len(s3_statements) == 1
    assert s3_statements[0]["Action"] == "s3:PutObject"
    resources = json.dumps(s3_statements[0]["Resource"])
    for suffix in ("/data/catalog-index.json", "/media/products/*", "/media/offer/*"):
        assert suffix in resources
    assert "incoming" not in resources
    for statement in statements:
        assert statement["Resource"] != "*"
        assert "*" not in json.dumps(statement["Action"])
    assert not _actions(statements) & {
        "dynamodb:PutItem",
        "dynamodb:DeleteItem",
        "s3:DeleteObject",
        "s3:GetObject",
    }


def test_admin_key_parameter_is_referenced_by_name_only() -> None:
    template = _template(_stack())
    functions = template.find_resources("AWS::Lambda::Function")
    for resource in functions.values():
        props = resource["Properties"]
        variables = props["Environment"]["Variables"]
        if props["Handler"].startswith("handlers.admin_"):
            assert variables["ADMIN_KEY_PARAMETER"] == (
                "/kedar-foods-app/prod/admin-key"
            )
        else:
            assert "ADMIN_KEY_PARAMETER" not in variables
    ssm_statement = next(
        s
        for s in _admin_statements(template, "handlers.admin_products.handler")
        if s["Action"] == "ssm:GetParameter"
    )
    assert "parameter/kedar-foods-app/prod/admin-key" in json.dumps(
        ssm_statement["Resource"]
    )
    assert template.find_resources("AWS::SSM::Parameter") == {}
