import os

import click

from cloudmesh.ai.command._shared.context import (
    console,
    debug_callback,
    verbose_callback,
)
from cloudmesh.ai.container.local.docker.DockerManager import DockerManager


@click.group()
@click.option(
    "--debug",
    is_flag=True,
    callback=debug_callback,
    expose_value=False,
    help="Enable debug logging",
)
@click.option(
    "--verbose",
    is_flag=True,
    callback=verbose_callback,
    expose_value=False,
    help="Print raw subprocess/SSH commands",
)
@click.pass_context
def container_group(ctx: click.Context) -> None:
    """Container management commands"""
    # Setup Docker manager
    # In this implementation, we instantiate DockerManager directly for the container group
    # Since Docker is a specific technology, OS_CLOUD=docker is implied here.
    try:
        # Mocking config as None for now, DockerManager handles its own init
        ctx.obj = DockerManager(config=None)
    except Exception as e:
        console.print(f"[bold red]Error initializing Docker manager: {e}[/bold red]")
        ctx.exit(1)

# Commands will be loaded here
def load_container_commands():
    from . import delete, info, list, run, stop, security_group, login, image, ip, restart, suspend
    container_group.add_command(list.list_containers, name="list")
    container_group.add_command(run.run_container, name="run")
    container_group.add_command(stop.stop_container, name="stop")
    container_group.add_command(delete.delete_container, name="delete")
    container_group.add_command(info.info_container, name="info")
    container_group.add_command(security_group.security_group, name="security-group")
    container_group.add_command(login.login_container, name="login")
    container_group.add_command(image.image, name="image")
    container_group.add_command(ip.ip, name="ip")
    container_group.add_command(restart.restart_container, name="restart")
    container_group.add_command(suspend.suspend, name="suspend")

load_container_commands()
