#!/usr/bin/env python
import subprocess
import re
import sys
from typing import List, Callable, Any, Tuple, Optional

def run_command(cmd: List[str]) -> Optional[str]:
    """Executes a shell command and returns its stdout."""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e.stderr or e.output}")
        return None

def verify_step(step_name: str, 
                cmd: List[str], 
                validation_fn: Callable[[Optional[str]], 
                bool]) -> bool:
    """Generic wrapper to run a command and validate its output."""
    print(f"\nChecking '{' '.join(cmd)}'...")
    output = run_command(cmd)
    print(79 * "=")
    print(output)
    print(79 * "=")
            
    if output is not None and validation_fn(output):
        print(f"✅ {step_name}: PASS")
        return True
    else:
        print(f"❌ {step_name}: FAIL")
        return False

def print_summary(results):
    print("\n" + "="*30)
    print(" VERIFICATION SUMMARY")
    print("="*30)
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{name:<20} : {status}")
        
    
    print("-" * 30)
    print(f"Total: {total} | Passed: {passed} | Failed: {total - passed}")
    print("="*30)
    
    if passed == total:
        print("OVERALL STATUS: SUCCESS")
    else:
        print("OVERALL STATUS: FAILURE")

def main():
    print("Starting verification of 'cmc vm' commands...\n")
    results = []

    # --- Phase 1: Discovery Tests (Independent) ---
    discovery_tests = [
        ("config", 
         ["cmc", "vm", "config"], 
         lambda out: "Configuration file location" in out),

        ("images", 
         ["cmc", "vm", "images"], 
         lambda out: len(out.strip()) > 0),

        ("flavors", 
         ["cmc", "vm", "flavors"], 
         lambda out: len(out.strip()) > 0),
    ]

    for name, cmd, validator in discovery_tests:
        success = verify_step(name, cmd, validator)
        results.append((name, success))

    # --- Phase 2: VM Lifecycle Tests (Dependent) ---
    print("\n--- Starting VM Lifecycle Tests ---")
    
    # Start VM
    print("\nChecking 'cmc vm start'...")
    start_out = run_command(["cmc", "vm", "start"])
    vm_name = None
    if start_out:
        match = re.search(r"VM ([\w-]+) started successfully", start_out)
        if match:
            vm_name = match.group(1)
            print(f"✅ start: PASS (VM: {vm_name})")
            results.append(("start", True))
        else:
            print("❌ start: FAIL (Could not parse VM name from output)")
            results.append(("start", False))
    else:
        print("❌ start: FAIL")
        results.append(("start", False))

    if not vm_name:
        print("\nSkipping subsequent tests as no VM could be started.")
        print_summary(results)
        return

    # Define Lifecycle tests using lambdas for dynamic commands/validation
    lifecycle_tests = [
        ("run --name", 
         lambda n: (["cmc", "vm", "run", "--name", n, "hostname"], 
         lambda out: out and out.strip()), 
         vm_name),

        ("run (last vm)", 
         lambda n: (["cmc", "vm", "run", "hostname"], 
         lambda out: out and out.strip()), 
         vm_name),

        ("info", 
         lambda n: (["cmc", "vm", "info", n], 
         lambda out: n in out), 
         vm_name),

        ("list", 
         lambda n: (["cmc", "vm", "list"], 
         lambda out: n in out and (hostname in out)), 
         vm_name),

        ("ssh-config", 
         lambda n: (["cmc", "vm", "ssh-config"], 
         lambda out: n in out), 
         vm_name),

        ("stop", 
         lambda n: (["cmc", "vm", "stop", "--name", n], 
         lambda out: out and "stopped" in out.lower()), 
         vm_name),

        ("delete", 
         lambda n: (["cmc", "vm", "delete", "--name", n], 
         lambda out: out and "deleted" in out.lower()), 
         vm_name),
    ]

    for name, template, context_name in lifecycle_tests:
        cmd, validator = template(context_name)
        success = verify_step(name, cmd, validator)
        results.append((name, success))

    print_summary(results)

if __name__ == "__main__":
    main()
