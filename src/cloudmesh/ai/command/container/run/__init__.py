import click
from cloudmesh.ai.command._shared.context import console

@click.command()
@click.option("--name", help="Name of the container")
@click.option("--image", default="ubuntu:latest", help="Docker image to use")
@click.option("--dockerfile", help="Path to the Dockerfile to build the image from")
@click.option("--network", help="Docker network to attach the container to")
@click.argument("cmd", nargs=-1)
@click.pass_context
def run_container(ctx: click.Context, cmd: tuple, name: str | None, image: str, dockerfile: str | None, network: str | None):
    """Run a Docker container."""
    manager = ctx.obj
    cmd_str = " ".join(cmd) if cmd else None
    result = manager.start(name=name, image=image, dockerfile=dockerfile, network=network, cmd=cmd_str)
    console.print(f"[green]{result}[/green]")
