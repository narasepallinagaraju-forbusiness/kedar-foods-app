"""CDK application entry point for frontend and backend infrastructure."""

from __future__ import annotations

import os
from collections.abc import Mapping

from aws_cdk import App, Environment, Tags
from backend_stack import BackendStack
from frontend_stack import FrontendStack


def _get_environment_name(value: object) -> str:
    if value is None:
        return "prod"
    if value not in ("prod", "dev"):
        raise ValueError(
            f"Invalid env context value {value!r}; expected 'prod' or 'dev'."
        )
    return str(value)


def create_app(context: Mapping[str, str] | None = None) -> App:
    app = App(context=dict(context) if context is not None else None)
    env_name = _get_environment_name(app.node.try_get_context("env"))
    domain_name = app.node.try_get_context("domainName")
    certificate_arn = app.node.try_get_context("certificateArn")
    site_origin = app.node.try_get_context("siteOrigin")

    environment = Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region="ap-south-1",
    )
    frontend_stack = FrontendStack(
        app,
        f"kedar-foods-app-{env_name}-frontend",
        env_name=env_name,
        domain_name=domain_name,
        certificate_arn=certificate_arn,
        site_origin=site_origin,
        env=environment,
        termination_protection=env_name == "prod",
    )
    backend_stack = BackendStack(
        app,
        f"kedar-foods-app-{env_name}-backend",
        env_name=env_name,
        cloudfront_domain_name=frontend_stack.distribution_domain_name,
        custom_domain_name=domain_name,
        env=environment,
        termination_protection=env_name == "prod",
    )
    backend_stack.add_dependency(frontend_stack)
    for stack in (frontend_stack, backend_stack):
        Tags.of(stack).add("Project", "kedar-foods-app")
        Tags.of(stack).add("Env", env_name)
    return app


if __name__ == "__main__":
    create_app().synth()
