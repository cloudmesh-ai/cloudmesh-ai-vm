import re

def main():
    file_path = 'src/cloudmesh/ai/command/vm.py'
    with open(file_path, 'r') as f:
        content = f.read()

    # Fix the broken f-strings where a quote was accidentally inserted after [bold red]
    # Example: f"[bold red]"Text[/bold red]" -> f"[bold red]Text[/bold red]"
    content = content.replace('f"[bold red]"', 'f"[bold red]')

    with open(file_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    main()
