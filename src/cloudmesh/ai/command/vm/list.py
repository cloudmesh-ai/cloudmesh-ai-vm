import csv
import io
import json
import click
import yaml
from ._shared.context import console, get_active_provider, vm_options
from ._shared.exceptions import handle_errors, VMCommandError
from ._shared.ui import render_table


def format_options(function):
    function = click.option("--format", "output_format",
                            type=click.Choice(["table", "json", "yaml", "csv"]))(function)
    for format_name in ("table", "csv", "yaml", "json"):
        function = click.option(f"--{format_name}", f"{format_name}_output",
                                is_flag=True)(function)
    return function


def choose_format(output_format, json_output, yaml_output, csv_output, table_output):
    flags = [name for name, selected in (
        ("json", json_output), ("yaml", yaml_output),
        ("csv", csv_output), ("table", table_output)
    ) if selected]
    if len(flags) > 1 or (flags and output_format):
        raise VMCommandError("Choose one output format.")
    return flags[0] if flags else output_format


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--all", is_flag=True, help="List VMs from all enabled providers")
@format_options
@handle_errors
def list_group(ctx, all, output_format, json_output, yaml_output, csv_output, table_output):
    """List VM resources."""
    if ctx.obj is None:
        from ._shared.context import VMContext
        ctx.obj = VMContext()
    ctx.obj.list_all = all
    ctx.obj.list_output_format = choose_format(
        output_format, json_output, yaml_output, csv_output, table_output
    ) or "table"
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_vms)


def vm_record(cloud_name, vm):
    if isinstance(vm, dict):
        return {**vm, "cloud": cloud_name}
    return {field: getattr(vm, field, None) for field in
            ("name", "status", "ip", "image", "flavor", "networks")} | {"cloud": cloud_name}


def render_records(records, output_format):
    columns = ["name", "status", "ip", "image", "flavor", "networks", "cloud"]
    if output_format == "json":
        click.echo(json.dumps(records, indent=2))
    elif output_format == "yaml":
        click.echo(yaml.safe_dump(records, sort_keys=False), nl=False)
    elif output_format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({
                key: json.dumps(value) if isinstance(value, (list, dict)) else value
                for key, value in record.items()
            })
        click.echo(buffer.getvalue(), nl=False)
    elif records:
        render_table("VMs", [column.title() for column in columns],
                     [[record.get(column) for column in columns] for record in records])
    else:
        console.print("No VMs found.")


@list_group.command(name="vms")
@click.pass_context
@format_options
@vm_options
@handle_errors
def list_vms(ctx, output_format=None, json_output=False, yaml_output=False,
             csv_output=False, table_output=False):
    """List VMs as a table, JSON, YAML, or CSV."""
    output_format = choose_format(
        output_format, json_output, yaml_output, csv_output, table_output
    ) or getattr(ctx.obj, "list_output_format", "table")
    records = []
    if getattr(ctx.obj, "list_all", False):
        from cloudmesh.ai.vm.providers import PROVIDER_MAP, get_provider
        from ._shared.context import state
        configured_clouds = state.db.get("clouds", {}) or {}
        for cloud_name in sorted(PROVIDER_MAP):
            config = configured_clouds.get(cloud_name, {})
            if config.get("enabled", False):
                provider = get_provider(cloud_name)
                records.extend(vm_record(cloud_name, vm) for vm in provider.list())
    else:
        provider = get_active_provider(ctx)
        records = [vm_record(provider.cloud_name, vm) for vm in provider.list()]
    render_records(records, output_format)


@list_group.command(name="regions")
@click.pass_context
@vm_options
@handle_errors
def list_regions(ctx):
    """List available regions."""
    provider = get_active_provider(ctx)
    regions = provider.list_regions()
    if regions:
        render_table("Regions", ["Region Name"], [[region] for region in regions])
    else:
        console.print("No regions found.")


cmd = list_group
