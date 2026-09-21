import click

@click.group()
def provider_group():
    """Manage VM cloud provider."""
    pass

cmd = provider_group
