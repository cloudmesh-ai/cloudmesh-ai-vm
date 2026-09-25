import click
import requests
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options
from ._shared.exceptions import handle_errors, VMCommandError
from ._shared.ui import render_table

PRESETS = {
    "web-server": [
        {"protocol": "tcp", "port": "80", "cidr": "0.0.0.0/0", "direction": "ingress"},
        {"protocol": "tcp", "port": "443", "cidr": "0.0.0.0/0", "direction": "ingress"},
        {"protocol": "tcp", "port": "22", "cidr": "CURRENT_IP", "direction": "ingress"},
    ],
    "db-server": [
        {"protocol": "tcp", "port": "5432", "cidr": "INTERNAL", "direction": "ingress"},
        {"protocol": "tcp", "port": "22", "cidr": "CURRENT_IP", "direction": "ingress"},
    ],
    "internal": [
        {"protocol": "all", "port": "all", "cidr": "INTERNAL", "direction": "ingress"},
    ]
}

def get_public_ip() -> str:
    """Fetch the current public IP of the machine."""
    try:
        return requests.get("https://api.ipify.org").text.strip()
    except Exception:
        return "0.0.0.0/0"

def resolve_cidr(cidr: str) -> str:
    """Resolves special CIDR placeholders."""
    if cidr == "CURRENT_IP":
        return f"{get_public_ip()}/32"
    if cidr == "INTERNAL":
        return "10.0.0.0/8"  # Simplified internal range
    return cidr

@click.group(invoke_without_command=True)
@click.pass_context
@vm_options
def security_group(ctx: click.Context):
    """Manage VM security groups."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_sgs)

@security_group.command(name="list")
@click.pass_context
@handle_errors
def list_sgs(ctx: click.Context):
    """List VM security groups."""
    provider = get_active_provider(ctx)
    sgs = provider.get_security_groups()
    if sgs:
        render_table("Security Groups", ["Name", "Description"], [[sg.get("name", "Unknown"), sg.get("description", "Unknown")] for sg in sgs])
    else:
        console.print("No security groups found.")

@security_group.command(name="info")
@click.argument("name")
@click.pass_context
@handle_errors
def sg_info(ctx: click.Context, name: str):
    """Get detailed information for a specific security group."""
    provider = get_active_provider(ctx)
    try:
        info = provider.get_security_group_info(name)
        if info:
            import json
            console.print(json.dumps(info, indent=4))
        else:
            console.print(f"No information found for security group {name}.")
    except Exception as e:
        console.print(f"Error getting info for security group {name}: {e}")

@security_group.command(name="create")
@click.argument("name")
@click.option("--description", default="", help="Description of the security group")
@click.option("--preset", type=click.Choice(list(PRESETS.keys()), case_sensitive=False), help="Use a pre-defined set of rules")
@click.pass_context
@handle_errors
def create_sg(ctx: click.Context, name: str, description: str, preset: Optional[str]):
    """Create a new security group."""
    provider = get_active_provider(ctx)
    if provider.create_security_group(name, description):
        console.print(f"[green]Security group {name} created successfully.[/green]")
        
        if preset:
            preset_name = preset.lower()
            rules = PRESETS.get(preset_name, [])
            console.print(f"Applying preset '{preset_name}'...")
            for rule in rules:
                cidr = resolve_cidr(rule["cidr"])
                port = rule["port"]
                try:
                    provider.add_security_group_rule(
                        name, rule["protocol"], port, cidr, rule["direction"]
                    )
                    console.print(f"  - Added {rule['protocol']} port {port} from {cidr} ({rule['direction']})")
                except Exception as e:
                    console.print(f"  [red]Failed to add rule {port}: {e}[/red]")
    else:
        raise VMCommandError(f"Failed to create security group {name}")

@security_group.command(name="delete")
@click.argument("name")
@click.pass_context
@handle_errors
def delete_sg(ctx: click.Context, name: str):
    """Delete a security group."""
    provider = get_active_provider(ctx)
    if provider.delete_security_group(name):
        console.print(f"[green]Security group {name} deleted successfully.[/green]")
    else:
        raise VMCommandError(f"Failed to delete security group {name}")


@security_group.command(name="add")
@click.argument("vm_name")
@click.argument("sg_name")
@click.pass_context
@handle_errors
def add_sg_to_vm(ctx: click.Context, vm_name: str, sg_name: str):
    """Associate a security group with a VM."""
    provider = get_active_provider(ctx)
    if provider.add_security_group_to_vm(vm_name, sg_name):
        console.print(f"[green]Security group {sg_name} added to VM {vm_name}.[/green]")
    else:
        raise VMCommandError(f"Failed to add security group {sg_name} to VM {vm_name}")

@security_group.command(name="remove")
@click.argument("vm_name")
@click.argument("sg_name")
@click.pass_context
@handle_errors
def remove_sg_from_vm(ctx: click.Context, vm_name: str, sg_name: str):
    """Remove a security group from a VM."""
    provider = get_active_provider(ctx)
    if provider.remove_security_group_from_vm(vm_name, sg_name):
        console.print(f"[green]Security group {sg_name} removed from VM {vm_name}.[/green]")
    else:
        raise VMCommandError(f"Failed to remove security group {sg_name} from VM {vm_name}")

@security_group.group(name="rule")
def rule_group():
    """Manage security group rules."""
    pass

@rule_group.command(name="list")
@click.argument("sg_name")
@click.pass_context
@handle_errors
def list_rules(ctx: click.Context, sg_name: str):
    """List rules for a security group."""
    provider = get_active_provider(ctx)
    rules = provider.list_security_group_rules(sg_name)
    if rules:
        # Rules in OpenStack are complex, let's simplify for the table
        table_data = []
        for r in rules:
            table_data.append([
                r.get("id", "N/A"),
                r.get("protocol", "N/A"),
                f"{r.get('port_range_min', 'N/A')}-{r.get('port_range_max', 'N/A')}",
                r.get("remote_ip_prefix", "N/A"),
                r.get("direction", "ingress")
            ])
        render_table(f"Rules for {sg_name}", ["ID", "Protocol", "Port Range", "Remote IP", "Direction"], table_data)
    else:
        console.print(f"No rules found for security group {sg_name}.")

@rule_group.command(name="add")
@click.argument("sg_name")
@click.option("--protocol", default="tcp", help="Protocol (tcp, udp, icmp)")
@click.option("--port", required=True, help="Destination port or port range")
@click.option("--cidr", default="0.0.0.0/0", help="Remote IP CIDR")
@click.option("--direction", type=click.Choice(["ingress", "egress"]), default="ingress", help="Traffic direction")
@click.pass_context
@handle_errors
def add_rule(ctx: click.Context, sg_name: str, protocol: str, port: str, cidr: str, direction: str):
    """Add a rule to a security group."""
    provider = get_active_provider(ctx)
    rule_id = provider.add_security_group_rule(sg_name, protocol, port, cidr, direction)
    console.print(f"[green]Rule added successfully. Rule ID: {rule_id}[/green]")

@rule_group.command(name="remove")
@click.argument("sg_name")
@click.argument("rule_id")
@click.pass_context
@handle_errors
def remove_rule(ctx: click.Context, sg_name: str, rule_id: str):
    """Remove a rule from a security group."""
    provider = get_active_provider(ctx)
    if provider.remove_security_group_rule(sg_name, rule_id):
        console.print(f"[green]Rule {rule_id} removed successfully from {sg_name}.[/green]")
    else:
        raise VMCommandError(f"Failed to remove rule {rule_id} from {sg_name}")

# Add the rule group to the main security_group command
security_group.add_command(rule_group)

cmd = security_group
