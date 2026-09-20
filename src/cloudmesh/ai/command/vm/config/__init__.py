import click

@click.group()
def config_group():
    """Manage VM CLI configuration."""
    pass

cmd = config_group
