"""Private S3 origins and CloudFront distribution for the frontend."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_certificatemanager as certificatemanager,
)
from aws_cdk import (
    aws_cloudfront as cloudfront,
)
from aws_cdk import (
    aws_cloudfront_origins as cloudfront_origins,
)
from aws_cdk import (
    aws_s3 as s3,
)
from constructs import Construct

if TYPE_CHECKING:
    from aws_cdk import Environment


_ONE_YEAR = Duration.days(365)


def _validate_site_origin(site_origin: str | None) -> None:
    if site_origin is None:
        return
    try:
        parsed = urlsplit(site_origin)
        port = parsed.port
    except ValueError as error:
        raise ValueError(
            "siteOrigin must be an exact https:// origin without a path, "
            "query, fragment, credentials, or wildcard."
        ) from error
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or "*" in parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or port == 0
        or any(character.isspace() for character in site_origin)
    ):
        raise ValueError(
            "siteOrigin must be an exact https:// origin without a path, "
            "query, fragment, credentials, or wildcard."
        )


def _validate_domain_and_certificate(
    env_name: str, domain_name: str | None, certificate_arn: str | None
) -> None:
    if env_name == "dev" and (domain_name is not None or certificate_arn is not None):
        raise ValueError("domainName and certificateArn are not allowed when env=dev.")
    if (domain_name is None) != (certificate_arn is None):
        raise ValueError("domainName and certificateArn must be supplied together.")
    if certificate_arn is not None and ":us-east-1:" not in certificate_arn:
        raise ValueError("certificateArn must be an ACM certificate ARN in us-east-1.")


def _cache_policy(
    scope: Construct,
    construct_id: str,
    policy_name: str,
    min_ttl: Duration,
    default_ttl: Duration,
    max_ttl: Duration,
) -> cloudfront.CachePolicy:
    return cloudfront.CachePolicy(
        scope,
        construct_id,
        cache_policy_name=policy_name,
        min_ttl=min_ttl,
        default_ttl=default_ttl,
        max_ttl=max_ttl,
        cookie_behavior=cloudfront.CacheCookieBehavior.none(),
        header_behavior=cloudfront.CacheHeaderBehavior.none(),
        query_string_behavior=cloudfront.CacheQueryStringBehavior.none(),
        enable_accept_encoding_brotli=True,
        enable_accept_encoding_gzip=True,
    )


class FrontendStack(Stack):
    """Deploy the static frontend, data/media storage, and CloudFront."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str,
        domain_name: str | None,
        certificate_arn: str | None,
        site_origin: str | None,
        env: Environment | None = None,
        termination_protection: bool = False,
    ) -> None:
        _validate_domain_and_certificate(env_name, domain_name, certificate_arn)
        _validate_site_origin(site_origin)
        super().__init__(
            scope,
            construct_id,
            env=env,
            termination_protection=termination_protection,
        )
        resource_prefix = f"kedar-foods-app-{env_name}"

        frontend_bucket = s3.Bucket(
            self,
            "FrontendBucket",
            bucket_name=f"{resource_prefix}-frontend",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        data_bucket = s3.Bucket(
            self,
            "DataMediaBucket",
            bucket_name=f"{resource_prefix}-data-media",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(7),
                    prefix="incoming/",
                    abort_incomplete_multipart_upload_after=Duration.days(1),
                )
            ],
            cors=(
                [
                    s3.CorsRule(
                        allowed_methods=[s3.HttpMethods.POST],
                        allowed_origins=[site_origin],
                        allowed_headers=["*"],
                    )
                ]
                if site_origin is not None
                else None
            ),
        )
        frontend_oac = cloudfront.S3OriginAccessControl(
            self,
            "FrontendOAC",
            origin_access_control_name=f"{resource_prefix}-oac-frontend",
        )
        data_media_oac = cloudfront.S3OriginAccessControl(
            self,
            "DataMediaOAC",
            origin_access_control_name=f"{resource_prefix}-oac-data-media",
        )
        frontend_origin = cloudfront_origins.S3BucketOrigin.with_origin_access_control(
            frontend_bucket,
            origin_access_control=frontend_oac,
        )
        data_origin = cloudfront_origins.S3BucketOrigin.with_origin_access_control(
            data_bucket,
            origin_access_control=data_media_oac,
        )

        html_cache_policy = _cache_policy(
            self,
            "HtmlCachePolicy",
            f"{resource_prefix}-cache-html",
            Duration.seconds(0),
            Duration.seconds(60),
            Duration.seconds(300),
        )
        data_cache_policy = _cache_policy(
            self,
            "DataCachePolicy",
            f"{resource_prefix}-cache-data",
            Duration.seconds(0),
            Duration.seconds(60),
            Duration.seconds(300),
        )
        immutable_cache_policy = _cache_policy(
            self,
            "ImmutableCachePolicy",
            f"{resource_prefix}-cache-immutable",
            _ONE_YEAR,
            _ONE_YEAR,
            _ONE_YEAR,
        )

        response_headers_policy = cloudfront.ResponseHeadersPolicy(
            self,
            "ResponseHeadersPolicy",
            response_headers_policy_name=f"{resource_prefix}-response-headers",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                content_type_options=cloudfront.ResponseHeadersContentTypeOptions(
                    override=True,
                ),
                frame_options=cloudfront.ResponseHeadersFrameOptions(
                    frame_option=cloudfront.HeadersFrameOption.DENY,
                    override=True,
                ),
                referrer_policy=cloudfront.ResponseHeadersReferrerPolicy(
                    referrer_policy=(
                        cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN
                    ),
                    override=True,
                ),
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=Duration.seconds(31536000),
                    include_subdomains=False,
                    preload=False,
                    override=True,
                ),
            ),
            custom_headers_behavior=cloudfront.ResponseCustomHeadersBehavior(
                custom_headers=[
                    cloudfront.ResponseCustomHeader(
                        header="Permissions-Policy",
                        value="camera=(), microphone=(), geolocation=()",
                        override=True,
                    ),
                    cloudfront.ResponseCustomHeader(
                        header="Content-Security-Policy-Report-Only",
                        value=(
                            "default-src 'self'; object-src 'none'; "
                            "base-uri 'self'; frame-ancestors 'none'"
                        ),
                        override=True,
                    ),
                ]
            ),
        )
        routing_function = cloudfront.Function(
            self,
            "RoutingFunction",
            code=cloudfront.FunctionCode.from_file(
                file_path=str(
                    Path(__file__).resolve().parent.parent
                    / "scripts"
                    / "cloudfront-routing-function.js"
                )
            ),
            function_name=f"{resource_prefix}-routing",
            runtime=cloudfront.FunctionRuntime.JS_2_0,
        )

        certificate = (
            certificatemanager.Certificate.from_certificate_arn(
                self,
                "Certificate",
                certificate_arn,
            )
            if certificate_arn is not None
            else None
        )
        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=frontend_origin,
                cache_policy=html_cache_policy,
                response_headers_policy=response_headers_policy,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                compress=True,
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=routing_function,
                        event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
                    )
                ],
            ),
            additional_behaviors={
                "/data/*": cloudfront.BehaviorOptions(
                    origin=data_origin,
                    cache_policy=data_cache_policy,
                    response_headers_policy=response_headers_policy,
                    viewer_protocol_policy=(
                        cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
                    ),
                    compress=True,
                ),
                "/media/*": cloudfront.BehaviorOptions(
                    origin=data_origin,
                    cache_policy=immutable_cache_policy,
                    response_headers_policy=response_headers_policy,
                    viewer_protocol_policy=(
                        cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
                    ),
                    compress=True,
                ),
                "/_next/*": cloudfront.BehaviorOptions(
                    origin=frontend_origin,
                    cache_policy=immutable_cache_policy,
                    response_headers_policy=response_headers_policy,
                    viewer_protocol_policy=(
                        cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
                    ),
                    compress=True,
                ),
            },
            price_class=cloudfront.PriceClass.PRICE_CLASS_200,
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=404,
                    response_page_path="/404.html",
                    ttl=Duration.seconds(10),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=404,
                    response_page_path="/404.html",
                    ttl=Duration.seconds(10),
                ),
            ],
            domain_names=[domain_name] if domain_name is not None else None,
            certificate=certificate,
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
        )
        self.distribution_domain_name = distribution.distribution_domain_name
        self.data_bucket_name = data_bucket.bucket_name

        CfnOutput(self, "FrontendBucketName", value=frontend_bucket.bucket_name)
        CfnOutput(self, "DataMediaBucketName", value=data_bucket.bucket_name)
        CfnOutput(self, "DistributionId", value=distribution.distribution_id)
        CfnOutput(self, "SiteDomain", value=self.distribution_domain_name)
