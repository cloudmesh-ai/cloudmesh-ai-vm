import re

def main():
    file_path = 'src/cloudmesh/ai/command/vm.py'
    with open(file_path, 'r') as f:
        content = f.read()

    # This regex finds the pattern: f"[bold red]" ... [/bold red]"
    # and replaces it with: f"[bold red] ... [/bold red]"
    # It captures everything between the quotes.
    pattern = r'f"\[bold red\]"(.*?)"\[/bold red\]"'
    
    # Wait, if the line is: console.print(f"[bold red]"Configuration...[/bold red]", stderr=True)
    # The pattern f"\[bold red\]"(.*?)"\[/bold red\]" will match:
    # Group 1: Configuration file not found at {CONFIG_PATH}
    # And the whole match is: f"[bold red]"Configuration file not found at {CONFIG_PATH}[/bold red]"
    
    # Let's try it.
    new_content = re.sub(pattern, r'f"[bold red]\1[/bold red]"', content)
    
    with open(file_path, 'w') as f:
        f.write(new_content)

if __name__ == "__main__":
    main()
