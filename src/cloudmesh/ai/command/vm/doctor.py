import click

from cloudmesh.ai.command._shared.context import (
    console,
    get_active_provider,
    vm_options,
)
from cloudmesh.ai.command._shared.exceptions import handle_errors
from cloudmesh.ai.command._shared.ui import render_table
# Import the new configuration validation helper
from cloudmesh.ai.vm.diagnostics.config_validator import run_all_config_checks


def _format_validation_result(result):
    """
    Convert provider.validate_config() output into a doctor status.

    Returns:
        tuple[str, str]: status and human-readable details.
    """
    if result is None or result == {}:
        return "PASS", "No configuration problems detected."

    if isinstance(result, bool):
        if result:
            return "PASS", "Configuration is valid."
        return "FAIL", "Configuration validation failed."

    if isinstance(result, dict):
        errors = result.get("errors", [])
        warnings = result.get("warnings", [])

        if errors:
            if isinstance(errors, (list, tuple)):
                details = "; ".join(str(item) for item in errors)
            else:
                details = str(errors)
            return "FAIL", details

        if warnings:
            if isinstance(warnings, (list, tuple)):
                details = "; ".join(str(item) for item in warnings)
            else:
                details = str(warnings)
            return "WARN", details

        # Some providers may return a dictionary with other validation
        # categories instead of explicit "errors" / "warnings".
        remaining = []
        for key, value in result.items():
            if value:
                if isinstance(value, (list, tuple)):
                    remaining.extend(
                        f"{key}: {item}" for item in value
                    )
                else:
                    remaining.append(f"{key}: {value}")

        if remaining:
            return "WARN", "; ".join(remaining)

        return "PASS", "No configuration problems detected."

    return "WARN", f"Unexpected validation result: {result}"


def _status_label(status):
    """Return a Rich-formatted status label."""
    styles = {
        "PASS": "[bold green]PASS[/bold green]",
        "FAIL": "[bold red]FAIL[/bold red]",
        "WARN": "[bold yellow]WARN[/bold yellow]",
        "SKIP": "[dim]SKIP[/dim]",
    }
    return styles.get(status, status)


@click.command()
@click.option(
    "--strict",
    is_flag=True,
    help="Exit with a non-zero status when a doctor check fails.",
)
@click.option(
    "--config",
    is_flag=True,
    help="Run exhaustive configuration validation (replicates smoke test).",
)
@click.pass_context
@vm_options
def doctor(
    ctx: click.Context,
    strict: bool = False,
    config: bool = False,
    **kwargs,
) -> None:
    """
    Diagnose the active VM provider without modifying any VM resources.

    Checks provider resolution, local requirements, configuration, and
    provider information.
    """
    rows = []
    failures = 0
    warnings = 0

    # 1. Resolve provider
    provider = get_active_provider(ctx)
    cloud_name = getattr(provider, "cloud_name", "unknown")

    rows.append(
        [
            "Provider",
            _status_label("PASS"),
            f"Resolved provider: {cloud_name}",
        ]
    )

    # 2. Check local provider requirements
    requirements_ok = None

    if hasattr(provider, "check_requirements"):
        try:
            requirements_ok = provider.check_requirements()

            if requirements_ok:
                rows.append(
                    [
                        "Requirements",
                        _status_label("PASS"),
                        "Required provider tools are available.",
                    ]
                )
            else:
                failures += 1
                rows.append(
                    [
                        "Requirements",
                        _status_label("FAIL"),
                        "One or more required provider tools are unavailable.",
                    ]
                )
        except Exception as exc:
            failures += 1
            rows.append(
                [
                    "Requirements",
                    _status_label("FAIL"),
                    f"{type(exc).__name__}: {exc}",
                ]
            )
    else:
        warnings += 1
        rows.append(
            [
                "Requirements",
                _status_label("SKIP"),
                "Provider does not implement check_requirements().",
            ]
        )

    # 3. Validate provider configuration
    if hasattr(provider, "validate_config"):
        try:
            validation = provider.validate_config()
            status, details = _format_validation_result(validation)

            if status == "FAIL":
                failures += 1
            elif status == "WARN":
                warnings += 1

            rows.append(
                [
                    "Configuration",
                    _status_label(status),
                    details,
                ]
            )
        except Exception as exc:
            failures += 1
            rows.append(
                [
                    "Configuration",
                    _status_label("FAIL"),
                    f"{type(exc).__name__}: {exc}",
                ]
            )
    else:
        warnings += 1
        rows.append(
            [
                "Configuration",
                _status_label("SKIP"),
                "Provider does not implement validate_config().",
            ]
        )

    # 4. Retrieve provider information.
    # Skip runtime provider queries if required local tools are unavailable.
    if requirements_ok is False:
        warnings += 1
        rows.append(
            [
                "Provider Info",
                _status_label("SKIP"),
                "Skipped because provider requirements are unavailable.",
            ]
        )

    elif hasattr(provider, "get_provider_info"):
        try:
            info = provider.get_provider_info()

            if info:
                rows.append(
                    [
                        "Provider Info",
                        _status_label("PASS"),
                        "Provider information retrieved successfully.",
                    ]
                )
            else:
                warnings += 1
                rows.append(
                    [
                        "Provider Info",
                        _status_label("WARN"),
                        "Provider returned no diagnostic information.",
                    ]
                )

        except Exception as exc:
            failures += 1
            rows.append(
                [
                    "Provider Info",
                    _status_label("FAIL"),
                    f"{type(exc).__name__}: {exc}",
                ]
            )

    else:
        warnings += 1
        rows.append(
            [
                "Provider Info",
                _status_label("SKIP"),
                "Provider does not implement get_provider_info().",
            ]
        )

    # -------------------------------------------------------------------
    # Optional exhaustive configuration validation (full_config flag).
    # -------------------------------------------------------------------
    if config:
        all_checks = run_all_config_checks()
        for section, checks in all_checks.items():
            for check_name, (status, details) in checks.items():
                # Row label combines the section and the individual check name
                row_label = f"{section}: {check_name}"
                rows.append([row_label, _status_label(status), details])
                if status == "FAIL":
                    failures += 1
                elif status == "WARN":
                    warnings += 1

    render_table(
        f"VM Doctor: {cloud_name}",
        ["Check", "Status", "Details"],
        rows,
    )

    if failures:
        console.print(
            f"\n[bold red]Doctor result: NEEDS ATTENTION[/bold red] "
            f"({failures} failed, {warnings} warning(s))"
        )
    elif warnings:
        console.print(
            f"\n[bold yellow]Doctor result: HEALTHY WITH WARNINGS[/bold yellow] "
            f"({warnings} warning(s))"
        )
    else:
        console.print(
            "\n[bold green]Doctor result: HEALTHY[/bold green]"
        )

    if strict and failures:
        ctx.exit(1)


# Required by the recursive VM command loader.
cmd = doctor
