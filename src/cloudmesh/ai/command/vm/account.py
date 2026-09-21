import click
from cloudmesh.ai.command.vm._shared.context import VMContext
from cloudmesh.ai.command.vm._shared.ui import console, render_table

@click.command()
@click.pass_context
def cmd(ctx: click.Context):
    """
    List account information and resource limits for the current VM provider.
    """
    # Get the active provider from the context
    provider = ctx.obj.get_provider()
    
    if not provider:
        console.print("[red]Error: No active provider found. Please set a provider using 'cmx vm provider set'.[/red]")
        return

    console.print(f"[bold blue]Fetching account information for provider: {provider.cloud_name}...[/bold blue]")
    
    # Call the provider's account info method
    info = provider.get_account_info()
    
    if not info:
        console.print("[yellow]No account information available for this provider.[/yellow]")
        return
    
    if "error" in info:
        console.print(f"[red]Error: {info['error']}[/red]")
        return

    # 1. Print Basic Account Information
    console.print("\\n[bold magenta]Account Details:[/bold magenta]")
    
    # Extract basic fields common to most providers
    basic_fields = {
        "Project ID": info.get("project_id"),
        "Project Name": info.get("project_name"),
        "Site/Domain": info.get("site") or info.get("domain_id"),
        "User ID": info.get("user_id"),
        "Allocation": info.get("allocation"),
    }
    
    for label, value in basic_fields.items():
        if value:
            console.print(f"[bold]{label}:[/bold] {value}")

    # 2. Print Quotas/Limits if available (common in OpenStack)
    quotas = info.get("quotas")
    if quotas:
        console.print("\\n[bold magenta]Resource Quotas/Limits:[/bold magenta]")
        
        # Prepare data for render_table
        # Quotas can be a dict of {resource: value} or a more complex structure
        rows = []
        if isinstance(quotas, dict):
            for resource, value in quotas.items():
                # Some providers might return a dict for value (e.g., {'limit': 10, 'used': 2})
                if isinstance(value, dict):
                    # Try to find 'limit' or 'used' in the value dict
                    limit = value.get('limit', 'N/A')
                    used = value.get('used', 'N/A')
                    rows.append([resource, limit, used])
                else:
                    rows.append([resource, value, "N/A"])
        
        if rows:
            render_table(
                title="VM Resource Limits",
                columns=["Resource", "Limit", "Used"],
                rows=rows,
                alignments=["left", "right", "right"]
            )
        else:
            console.print("[yellow]No detailed quota information available.[/yellow]")
    else:
        # If no quotas, but we have basic info, just finish
        pass

    console.print("\\n")
