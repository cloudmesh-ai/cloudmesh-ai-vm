import os
import click
from rich.panel import Panel
from rich.markdown import Markdown
from .context import console, get_active_provider, vm_options

def show_markdown_cost(cloud_name):
    """Helper to render the markdown cost template for a given cloud."""
    # The templates are expected to be in src/cloudmesh/ai/command/vm/template/
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "template"))
    cost_file = os.path.join(template_dir, f"cost-{cloud_name}.md")

    if not os.path.exists(cost_file):
        console.print(f"[bold red]Error: Cost information not found for cloud '{cloud_name}'.[/bold red]")
        console.print(f"Template file missing at: {cost_file}")
        return

    try:
        with open(cost_file, 'r') as f:
            content = f.read()
        
        md = Markdown(content)
        
        console.print("\n")
        console.print(Panel(
            md, 
            title=f"[bold cyan]{cloud_name.upper()} Cost Details[/bold cyan]", 
            border_style="cyan", 
            expand=False,
            padding=(1, 2)
        ))
        console.print("\n")
    except Exception as e:
        console.print(f"[bold red]Error reading cost template: {e}[/bold red]")

@click.command()
@click.argument("action", required=False)
@click.option("--flavor", help="Override VM flavor/size for cost estimation")
@click.option("--num_instances", type=int, help="Number of instances for cost estimation")
@click.option("--hours_per_day", type=int, help="Hours per day for cost estimation")
@click.option("--days_per_week", type=int, help="Days per week for cost estimation")
@click.option("--weeks", type=int, help="Number of weeks for cost estimation")
@vm_options
def cost(ctx, action, **kwargs):
    """Returns the cost for the active cloud provider"""
    provider = get_active_provider(ctx)
    cloud_name = provider.cloud_name

    # 1. If 'help' action is specified, show the markdown template
    if action == "help":
        show_markdown_cost(cloud_name)
        return

    # Collect overrides from kwargs for the provider
    overrides = {
        "flavor": kwargs.get("flavor"),
        "num_instances": kwargs.get("num_instances"),
        "hours_per_day": kwargs.get("hours_per_day"),
        "days_per_week": kwargs.get("days_per_week"),
        "weeks": kwargs.get("weeks"),
    }
    # Filter out None values
    overrides = {k: v for k, v in overrides.items() if v is not None}

    # 2. Try the provider's dynamic get_cost method first
    try:
        dynamic_cost = provider.get_cost(**overrides)
    except Exception as e:
        console.print(f"[bold red]Error during cost calculation: {e}[/bold red]")
        return

    if dynamic_cost:
        # Handle dictionary format {value, unit, details}
        if isinstance(dynamic_cost, dict):
            value = dynamic_cost.get("value", "Unknown")
            unit = dynamic_cost.get("unit")
            details = dynamic_cost.get("details")
            
            display_text = f"Cost: {value} {unit if unit else ''}".strip()
            if details:
                display_text += f"\n\n{details}"
        else:
            display_text = str(dynamic_cost)

        console.print("\n")
        console.print(Panel(
            display_text,
            title=f"[bold cyan]{cloud_name.upper()} Cost Estimation[/bold cyan]",
            border_style="cyan",
            expand=False,
            padding=(1, 2)
        ))
        console.print("\n")
        return

    # 3. Fallback to the static markdown template
    show_markdown_cost(cloud_name)
