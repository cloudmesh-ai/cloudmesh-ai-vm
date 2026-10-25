import click
from cloudmesh.ai.command._shared.context import console

@click.group()
def security_group():
    """Manage Docker networks (as security groups)."""
    pass

@security_group.command("create")
@click.argument("name")
@click.pass_context
def create_sg(ctx: click.Context, name: str):
    """Create a Docker network."""
    manager = ctx.obj
    if manager.create_network(name):
        console.print(f"[green]Security group (network) {name} created successfully.[/green]")
    else:
        console.print(f"[red]Failed to create security group {name}.[/red]")

@security_group.command("list")
@click.pass_context
def list_sg(ctx: click.Context):
    """List Docker networks."""
    manager = ctx.obj
    networks = manager.list_networks()
    if not networks:
        console.print("No networks found.")
        return
    
    console.print("[bold]Docker Networks (Security Groups):[/bold]")
    for net in networks:
        console.print(f"- {net['name']} ({net['id']})")

@security_group.command("delete")
@click.argument("name")
@click.pass_context
def delete_sg(ctx: click.Context, name: str):
    """Delete a Docker network."""
    manager = ctx.obj
    if manager.delete_network(name):
        console.print(f"[green]Security group (network) {name} deleted successfully.[/green]")
    else:
        console.print(f"[red]Failed to delete security group {name}.[/red]")
