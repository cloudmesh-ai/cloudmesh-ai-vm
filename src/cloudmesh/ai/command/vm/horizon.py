import click
import webbrowser
from ._shared.context import VMContext

URL_MAP = {
    "CHI@TACC": "https://chi.tacc.chameleoncloud.org",
    "CHI@UC": "https://chi.uc.chameleoncloud.org",
    "CHI@NU": "https://chi.nu.chameleoncloud.org",
    "CHI@NCAR": "https://chi.ncar.chameleoncloud.org",
    "KVM@TACC": "https://kvm.tacc.chameleoncloud.org",
    "CHI@NRP": "https://chi.nrp.chameleoncloud.org",
    "Jetstream": "https://js2.jetstream-cloud.org/",
}

@click.command()
@click.option("--site", type=click.Choice(list(URL_MAP.keys()), case_sensitive=False), help="Specify the cloud site")
@click.pass_context
def cmd(ctx: click.Context, site: str = None) -> None:
    """Open the Horizon dashboard for the active cloud provider."""
    from ._shared.context import state
    
    # 1. Determine which site to use
    target_site = site
    
    if not target_site:
        # Try to get the active provider from context
        active_provider = ctx.obj.cloud_override or getattr(state.config, "default_cloud", "multipass") or "multipass"
        
        if active_provider == "chameleon":
            # Look up the site in the chameleon config
            chameleon_config = getattr(state.config, "chameleon", {})
            target_site = getattr(chameleon_config, "site", None)
        elif active_provider == "jetstream":
            target_site = "Jetstream"
            
    # 2. Resolve the URL
    if target_site:
        # Match the input (potentially lowercased by click.Choice) to the keys in URL_MAP
        lookup_key = next((k for k in URL_MAP.keys() if k.lower() == target_site.lower()), None)
        if lookup_key:
            url = URL_MAP[lookup_key]
            click.echo(f"Opening Horizon for {lookup_key}...")
            webbrowser.open(url)
            return

    click.echo("Could not determine the target cloud site.")
    click.echo("Available sites:")
    for s in URL_MAP.keys():
        click.echo(f"  - {s}")
    click.echo("\nUse 'cmx vm horizon --site <SITE>' to open a specific one.")
