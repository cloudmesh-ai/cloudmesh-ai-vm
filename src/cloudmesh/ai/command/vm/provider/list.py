import click
from .._shared.context import console, state, CONFIG_PATH
from .._shared.exceptions import handle_errors
from .._shared.ui import render_table

@click.command(name="list")
@click.pass_context
@handle_errors
def list_providers(ctx: click.Context):
    """List all supported VM providers and their configuration status."""
    from cloudmesh.ai.vm.providers import PROVIDER_MAP, PROVIDER_METADATA
    
    # Access the current configuration from the state proxy
    config = state.config
    configured_clouds = config.db.get("clouds", {}) if config else {}
    default_cloud = config.db.get("default_cloud", "multipass") if config else None
    
    # Prepare rows for the provider support matrix
    rows = []
    # Iterate over the supported providers defined in metadata
    sorted_providers = sorted(PROVIDER_METADATA.keys())
    
    for p_name in sorted_providers:
        meta = PROVIDER_METADATA.get(p_name, {})
        
        # Format the provider name for display
        display_name = p_name.capitalize()
        if p_name == "aws": display_name = "AWS"
        elif p_name == "azure": display_name = "Azure"
        elif p_name == "google": display_name = "Google"
        elif p_name == "wsl2": display_name = "WSL2"
        elif p_name == "vbox": display_name = "VirtualBox"
        elif p_name == "chameleon": display_name = "Chameleon Cloud"
        elif p_name == "jetstream": display_name = "Jetstream"
        
        # Check if the provider is the default
        is_default = "⭐" if p_name == default_cloud else ""
        
        # Check if the provider is defined in clouds.yaml AND has enabled=True
        cloud_cfg = configured_clouds.get(p_name)
        is_enabled_val = False
        if cloud_cfg:
            if hasattr(cloud_cfg, 'enabled'):
                is_enabled_val = cloud_cfg.enabled
            elif isinstance(cloud_cfg, dict):
                is_enabled_val = cloud_cfg.get('enabled', False)
        
        is_enabled = "🟢" if is_enabled_val else "🔴"
        
        rows.append([
            is_default,
            display_name,
            is_enabled,
            meta.get("lifecycle", "🔴"),
            meta.get("remote_exec", "🔴"),
            meta.get("status", "Unknown")
        ])
    
    # Define alignments for the columns:
    # ["", "Provider", "Enabled", "Lifecycle", "Remote Exec", "Status"]
    # We center the status icons but leave descriptions left-aligned.
    alignments = ["center", "left", "center", "center", "left", "left"]
    
    render_table(
        "Provider Support & Configuration Matrix", 
        ["", "Provider", "Enabled", "Lifecycle", "Remote Exec", "Status"], 
        rows,
        alignments=alignments
    )
    
    if default_cloud:
        console.print(f"\n[bold]Default cloud provider:[/bold] [bold green]{default_cloud}[/bold green]")
    
    console.print(f"[bold]Cloudmesh Config file path:[/bold] [dim]~/.config/cloudmesh/clouds.yaml[/dim]")
    console.print(f"[bold]Openstack Config file path:[/bold] [dim]~/.config/openstack/clouds.yaml[/dim]")

cmd = list_providers
