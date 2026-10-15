import click

@click.group()
def ip_group():
    """Manage VM floating IPs."""
    pass

cmd = ip_group
