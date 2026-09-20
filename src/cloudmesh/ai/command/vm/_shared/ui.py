from rich.console import Console
from rich.table import Table

console = Console()

def render_table(title: str, columns: list, rows: list):
    """Renders a rich table for CLI output."""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(item) for item in row])
    console.print(table)
