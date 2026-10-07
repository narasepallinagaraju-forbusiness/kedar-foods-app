"""CDK assertions for the frontend stack and its context validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from aws_cdk import App, Environment, Stack
from aws_cdk.assertions import Template
from aws_cdk.cloud_assembly_schema import AwsCloudFormationStackProperties
from frontend_stack import FrontendStack

from app import create_app

ROOT = Path(__file__).resolve().parents[2]
ROUTING_FUNCTION = ROOT / "scripts" / "cloudfront-routing-function.js"


def _stack(
    *,
    env_name: str = "prod",
    domain_name: str | None = None,
    certificate_arn: str | None = None,
    site_origin: str | None = None,
) -> FrontendStack:
    app = App()
    return FrontendStack(
        app,
        f"Frontend-{env_name}",
        env_name=env_name,
        domain_name=domain_name,
        certificate_arn=certificate_arn,
        site_origin=site_origin,
        env=Environment(account="123456789012", region="ap-south-1"),
    )


def _template(stack: FrontendStack) -> Template:
    return Template.from_stack(stack)


def test_buckets_are_private_retain_ssl_enforced_and_expire_incoming() -> None:
    template = _template(_stack())
    buckets = template.find_resources("AWS::S3::Bucket")
    assert len(buckets) == 2
    assert {
        bucket["Properties"]["BucketName"] for bucket in buckets.values()
    } == {
        "kedar-foods-app-prod-frontend",
        "kedar-foods-app-prod-data-media",
    }
    for bucket in buckets.values():
        properties = bucket["Properties"]
        assert properties["PublicAccessBlockConfiguration"] == {
            "BlockPublicAcls": True,
            "BlockPublicPolicy": True,
            "IgnorePublicAcls": True,
            "RestrictPublicBuckets": True,
        }
    assert any(
        "LifecycleConfiguration" in bucket["Properties"]
        and bucket["Properties"]["LifecycleConfiguration"]["Rules"]
        == [
            {
                "AbortIncompleteMultipartUpload": {
                    "DaysAfterInitiation": 1,
                },
                "ExpirationInDays": 7,
                "Prefix": "incoming/",
                "Status": "Enabled",
            }
        ]
        for bucket in buckets.values()
    )
    template.resource_count_is("AWS::S3::BucketPolicy", 2)
    for policy in template.find_resources("AWS::S3::BucketPolicy").values():
        statements = policy["Properties"]["PolicyDocument"]["Statement"]
        assert any(
            statement.get("Effect") == "Deny"
            and statement.get("Condition", {})
            .get("Bool", {})
            .get("aws:SecureTransport")
            in (False, "false")
            for statement in statements
        )
        assert not any(
            statement.get("Effect") == "Allow"
            and statement.get("Principal") in ("*", {"AWS": "*"})
            for statement in statements
        )


def test_cloudfront_origins_use_oac_without_oai() -> None:
    template = _template(_stack())
    distributions = template.find_resources("AWS::CloudFront::Distribution")
    assert len(distributions) == 1
    template.resource_count_is("AWS::CloudFront::OriginAccessControl", 2)
    oac_names = {
        resource["Properties"]["OriginAccessControlConfig"]["Name"]
        for resource in template.find_resources(
            "AWS::CloudFront::OriginAccessControl"
        ).values()
    }
    assert oac_names == {
        "kedar-foods-app-prod-oac-frontend",
        "kedar-foods-app-prod-oac-data-media",
    }
    template.resource_count_is("AWS::CloudFront::CloudFrontOriginAccessIdentity", 0)
    origins = next(iter(distributions.values()))["Properties"]["DistributionConfig"][
        "Origins"
    ]
    assert len(origins) == 2
    assert template.find_resources("AWS::CloudFront::OriginAccessControl")
    for origin in origins:
        assert origin["OriginAccessControlId"]
        s3_origin = origin.get("S3OriginConfig", {})
        assert s3_origin.get("OriginAccessIdentity", "") == ""


def test_behavior_origins_map_to_expected_buckets() -> None:
    template = _template(_stack())
    resources = template.to_json()["Resources"]
    distribution = next(
        iter(template.find_resources("AWS::CloudFront::Distribution").values())
    )["Properties"]["DistributionConfig"]
    bucket_ids = {
        "frontend": next(
            logical_id
            for logical_id, resource in resources.items()
            if resource["Type"] == "AWS::S3::Bucket"
            and logical_id.startswith("FrontendBucket")
        ),
        "data": next(
            logical_id
            for logical_id, resource in resources.items()
            if resource["Type"] == "AWS::S3::Bucket"
            and logical_id.startswith("DataMediaBucket")
        ),
    }
    origins_by_id = {
        origin["Id"]: origin for origin in distribution["Origins"]
    }
    domain_bucket_ids = {
        origin["Id"]: origin["DomainName"]["Fn::GetAtt"][0]
        for origin in distribution["Origins"]
    }
    assert set(domain_bucket_ids.values()) == set(bucket_ids.values())
    assert domain_bucket_ids[
        distribution["DefaultCacheBehavior"]["TargetOriginId"]
    ] == bucket_ids["frontend"]

    target_bucket_by_pattern = {
        behavior["PathPattern"]: domain_bucket_ids[behavior["TargetOriginId"]]
        for behavior in distribution["CacheBehaviors"]
    }
    assert target_bucket_by_pattern["/data/*"] == bucket_ids["data"]
    assert target_bucket_by_pattern["/media/*"] == bucket_ids["data"]
    assert target_bucket_by_pattern["/_next/*"] == bucket_ids["frontend"]
    assert (
        origins_by_id[
            distribution["DefaultCacheBehavior"]["TargetOriginId"]
        ]["DomainName"]
        != origins_by_id[
            next(
                origin_id
                for origin_id, bucket_id in domain_bucket_ids.items()
                if bucket_id == bucket_ids["data"]
            )
        ]["DomainName"]
    )


def test_behaviors_reference_cache_policies_with_expected_ttls() -> None:
    template = _template(_stack())
    resources = template.to_json()["Resources"]
    distribution = next(
        iter(template.find_resources("AWS::CloudFront::Distribution").values())
    )["Properties"]["DistributionConfig"]
    cache_ttls = {
        logical_id: (
            resource["Properties"]["CachePolicyConfig"]["MinTTL"],
            resource["Properties"]["CachePolicyConfig"]["DefaultTTL"],
            resource["Properties"]["CachePolicyConfig"]["MaxTTL"],
        )
        for logical_id, resource in resources.items()
        if resource["Type"] == "AWS::CloudFront::CachePolicy"
    }

    def policy_ttls(behavior: dict[str, Any]) -> tuple[int, int, int]:
        policy_ref = behavior["CachePolicyId"]["Ref"]
        return cache_ttls[policy_ref]

    behavior_by_pattern = {
        behavior["PathPattern"]: behavior
        for behavior in distribution["CacheBehaviors"]
    }
    assert policy_ttls(distribution["DefaultCacheBehavior"]) == (0, 60, 300)
    assert policy_ttls(behavior_by_pattern["/data/*"]) == (0, 60, 300)
    assert policy_ttls(behavior_by_pattern["/media/*"]) == (
        31536000,
        31536000,
        31536000,
    )
    assert policy_ttls(behavior_by_pattern["/_next/*"]) == (
        31536000,
        31536000,
        31536000,
    )


def test_only_default_behavior_has_viewer_request_function_association() -> None:
    template = _template(_stack())
    distribution = next(
        iter(template.find_resources("AWS::CloudFront::Distribution").values())
    )["Properties"]["DistributionConfig"]
    default_associations = distribution["DefaultCacheBehavior"].get(
        "FunctionAssociations", []
    )
    assert len(default_associations) == 1
    assert default_associations[0]["EventType"] == "viewer-request"
    assert default_associations[0]["FunctionARN"]["Fn::GetAtt"][0].startswith(
        "RoutingFunction"
    )
    assert all(
        not behavior.get("FunctionAssociations", [])
        for behavior in distribution["CacheBehaviors"]
    )


def test_bucket_policy_allows_only_cloudfront_object_reads() -> None:
    template = _template(_stack())
    template.resource_count_is("AWS::S3::BucketPolicy", 2)
    for policy in template.find_resources("AWS::S3::BucketPolicy").values():
        statements = policy["Properties"]["PolicyDocument"]["Statement"]
        allow_statements = [
            statement
            for statement in statements
            if statement.get("Effect") == "Allow"
        ]
        assert len(allow_statements) == 1
        statement = allow_statements[0]
        assert statement["Action"] == "s3:GetObject"
        assert statement["Principal"] == {
            "Service": "cloudfront.amazonaws.com",
        }
        assert "AWS:SourceArn" in statement["Condition"]["StringEquals"]


def test_cors_is_absent_by_default_and_exact_https_post_when_configured() -> None:
    default_template = _template(_stack())
    bucket_resources = default_template.find_resources("AWS::S3::Bucket").values()
    assert all(
        "CorsConfiguration" not in bucket["Properties"] for bucket in bucket_resources
    )

    configured_template = _template(_stack(site_origin="https://shop.example.com"))
    configured_bucket = next(
        bucket
        for bucket in configured_template.find_resources("AWS::S3::Bucket").values()
        if "CorsConfiguration" in bucket["Properties"]
    )
    cors_rule = configured_bucket["Properties"]["CorsConfiguration"]["CorsRules"][0]
    assert cors_rule["AllowedOrigins"] == ["https://shop.example.com"]
    assert cors_rule["AllowedMethods"] == ["POST"]
    assert "*" not in cors_rule["AllowedOrigins"]


@pytest.mark.parametrize(
    "site_origin",
    [
        "http://shop.example.com",
        "https://*.example.com",
        "https://shop.example.com/",
        "https://shop.example.com/path",
        "https://shop.example.com?query=1",
        "https://user@shop.example.com",
        "https://shop.example.com:0",
        "https://shop.example.com:invalid",
        "https://shop .example.com",
    ],
)
def test_invalid_site_origin_is_rejected(site_origin: str) -> None:
    with pytest.raises(ValueError, match="siteOrigin must be an exact https:// origin"):
        _stack(site_origin=site_origin)


def test_cache_policies_have_expected_ttls_and_empty_cache_keys() -> None:
    template = _template(_stack())
    policies = template.find_resources("AWS::CloudFront::CachePolicy")
    policy_properties = [
        resource["Properties"]["CachePolicyConfig"] for resource in policies.values()
    ]
    assert {
        config["Name"] for config in policy_properties
    } == {
        "kedar-foods-app-prod-cache-html",
        "kedar-foods-app-prod-cache-data",
        "kedar-foods-app-prod-cache-immutable",
    }
    assert sorted(
        (
            config["MinTTL"],
            config["DefaultTTL"],
            config["MaxTTL"],
        )
        for config in policy_properties
    ) == [(0, 60, 300), (0, 60, 300), (31536000, 31536000, 31536000)]
    for config in policy_properties:
        parameters = config["ParametersInCacheKeyAndForwardedToOrigin"]
        assert parameters["CookiesConfig"]["CookieBehavior"] == "none"
        assert parameters["HeadersConfig"]["HeaderBehavior"] == "none"
        assert parameters["QueryStringsConfig"]["QueryStringBehavior"] == "none"
        assert parameters["EnableAcceptEncodingBrotli"] is True
        assert parameters["EnableAcceptEncodingGzip"] is True


def test_distribution_behaviors_errors_and_function_source() -> None:
    template = _template(_stack())
    distributions = template.find_resources("AWS::CloudFront::Distribution")
    distribution = next(iter(distributions.values()))["Properties"][
        "DistributionConfig"
    ]
    behaviors = distribution["CacheBehaviors"]
    assert {behavior["PathPattern"] for behavior in behaviors} == {
        "/data/*",
        "/media/*",
        "/_next/*",
    }
    assert (
        distribution["DefaultCacheBehavior"]["ViewerProtocolPolicy"]
        == "redirect-to-https"
    )
    assert all(
        behavior["ViewerProtocolPolicy"] == "redirect-to-https"
        for behavior in behaviors
    )
    assert distribution["PriceClass"] == "PriceClass_200"
    assert distribution["CustomErrorResponses"] == [
        {
            "ErrorCachingMinTTL": 10,
            "ErrorCode": 403,
            "ResponseCode": 404,
            "ResponsePagePath": "/404.html",
        },
        {
            "ErrorCachingMinTTL": 10,
            "ErrorCode": 404,
            "ResponseCode": 404,
            "ResponsePagePath": "/404.html",
        },
    ]

    functions = template.find_resources("AWS::CloudFront::Function")
    function = next(iter(functions.values()))["Properties"]
    assert function["Name"] == "kedar-foods-app-prod-routing"
    assert function["FunctionConfig"]["Runtime"] == "cloudfront-js-2.0"
    assert function["FunctionCode"] == ROUTING_FUNCTION.read_bytes().decode("utf-8")


def test_distribution_sets_minimum_tls_protocol_for_custom_domain() -> None:
    domain_name = "shop.example.com"
    certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/abcd"
    template = _template(
        _stack(
            domain_name=domain_name,
            certificate_arn=certificate_arn,
        )
    )
    distribution = next(
        iter(template.find_resources("AWS::CloudFront::Distribution").values())
    )["Properties"]["DistributionConfig"]
    assert distribution["Aliases"] == [domain_name]
    assert (
        distribution["ViewerCertificate"]["AcmCertificateArn"] == certificate_arn
    )
    assert distribution["ViewerCertificate"]["MinimumProtocolVersion"] == "TLSv1.2_2021"


def test_response_headers_policy_has_required_security_headers() -> None:
    template = _template(_stack())
    policy = next(
        iter(template.find_resources("AWS::CloudFront::ResponseHeadersPolicy").values())
    )["Properties"]["ResponseHeadersPolicyConfig"]
    assert policy["Name"] == "kedar-foods-app-prod-response-headers"
    security_headers = policy["SecurityHeadersConfig"]
    hsts = security_headers["StrictTransportSecurity"]
    assert hsts["AccessControlMaxAgeSec"] == 31536000
    assert hsts["IncludeSubdomains"] is False
    assert hsts["Preload"] is False
    assert security_headers["ContentTypeOptions"]["Override"] is True
    assert security_headers["FrameOptions"]["FrameOption"] == "DENY"
    assert (
        security_headers["ReferrerPolicy"]["ReferrerPolicy"]
        == "strict-origin-when-cross-origin"
    )
    custom_headers = {
        item["Header"]: item["Value"] for item in policy["CustomHeadersConfig"]["Items"]
    }
    assert custom_headers["Permissions-Policy"]
    assert custom_headers["Content-Security-Policy-Report-Only"]
    assert "Content-Security-Policy" not in custom_headers


@pytest.mark.parametrize(
    ("domain_name", "certificate_arn"),
    [
        ("shop.example.com", None),
        (None, "arn:aws:acm:us-east-1:123456789012:certificate/abcd"),
    ],
)
def test_domain_and_certificate_must_be_supplied_together(
    domain_name: str | None, certificate_arn: str | None
) -> None:
    with pytest.raises(ValueError, match="must be supplied together"):
        _stack(domain_name=domain_name, certificate_arn=certificate_arn)


def test_certificate_must_be_in_us_east_1() -> None:
    with pytest.raises(
        ValueError, match="certificateArn must be an ACM certificate ARN in us-east-1"
    ):
        _stack(
            domain_name="shop.example.com",
            certificate_arn="arn:aws:acm:ap-south-1:123456789012:certificate/abcd",
        )


def test_dev_rejects_domain_and_certificate() -> None:
    with pytest.raises(ValueError, match="not allowed when env=dev"):
        _stack(
            env_name="dev",
            domain_name="shop.example.com",
            certificate_arn="arn:aws:acm:us-east-1:123456789012:certificate/abcd",
        )


def test_invalid_env_context_is_rejected() -> None:
    with pytest.raises(ValueError, match="expected 'prod' or 'dev'"):
        create_app({"env": "staging"})


def test_prod_stack_has_termination_protection_and_tags() -> None:
    app = create_app()
    stack_name = "kedar-foods-app-prod-frontend"
    stack_construct = app.node.try_find_child(stack_name)
    assert isinstance(stack_construct, Stack)
    assembly = app.synth()
    artifact = assembly.get_stack_by_name(stack_name)
    properties = artifact.manifest.properties
    assert isinstance(properties, AwsCloudFormationStackProperties)
    assert properties.termination_protection is True

    resources = Template.from_stack(stack_construct).to_json()["Resources"]
    tags = [
        tag
        for resource in resources.values()
        for tag in resource.get("Properties", {}).get("Tags", [])
    ]
    assert {"Key": "Project", "Value": "kedar-foods-app"} in tags
    assert {"Key": "Env", "Value": "prod"} in tags
