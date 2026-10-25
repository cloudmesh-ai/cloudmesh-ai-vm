import click
from cloudmesh.ai.command._shared.context import console

@click.group()
def ip():
    """Manage container IP addresses."""
    pass

@ip.command("list")
@click.pass_context
def list_ips(ctx: click.Context):
    """List IP addresses of running containers."""
    manager = ctx.obj
    ips = manager.list_container_ips()
    if not ips:
        console.print("No running containers found.")
        return
    
    console.print("[bold]Container IP Addresses:[/bold]")
    for item in ips:
        console.print(f"- {item['name']}: {item['ip']}")
