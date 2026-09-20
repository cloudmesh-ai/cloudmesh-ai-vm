import re

def main():
    file_path = 'src/cloudmesh/ai/command/vm.py'
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    fixed_lines = []
    for line in lines:
        # We want to transform:
        # console.print(f"[bold red]"TEXT[/bold red]", stderr=True)
        # into:
        # console.print(f"[bold red]TEXT[/bold red]", stderr=True)
        
        if 'f"[bold red]"' in line and '[/bold red]"' in line:
            # Use regex to replace the patterns
            line = line.replace('f"[bold red]"', 'f"[bold red]')
            line = line.replace('[/bold red]"', '[/bold red]"')
        fixed_lines.append(line)
    
    with open(file_path, 'w') as f:
        f.writelines(fixed_lines)

if __name__ == "__main__":
    main()
