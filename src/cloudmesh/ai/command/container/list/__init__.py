import click

from cloudmesh.ai.command._shared.context import console


@click.command()
@click.pass_context
def list_containers(ctx: click.Context):
    """List all Docker containers."""
    manager = ctx.obj
    containers = manager.list()
    if not containers:
        console.print("[yellow]No containers found.[/yellow]")
        return

    console.print(f"[bold]Containers on cloud: [blue]{manager.cloud_name}[/blue][/bold]")
    for c in containers:
        console.print(f"- {c['name']} ({c['id']}) Status: {c['status']} Image: {c['image']}")

