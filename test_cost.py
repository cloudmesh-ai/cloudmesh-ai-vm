import sys
from click.testing import CliRunner
from cloudmesh.ai.command.vm import vm_group
from cloudmesh.ai.vm.config_models import GlobalConfig
from cloudmesh.ai.vm.logger import logger

# Mock the state and config
import cloudmesh.ai.command.vm as vm_cmd
vm_cmd.state.config = GlobalConfig(default_cloud="jetstream")
vm_cmd.console = None # Avoid rich issues in tests

def test_cost_command():
    runner = CliRunner()
    
    # Test 1: Basic cost command (should fall back to markdown or return cost)
    print("Testing: cmc vm cost")
    result = runner.invoke(vm_group, ['cost'])
    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.output}")
    
    # Test 2: Cost command with parameters
    print("\nTesting: cmc vm cost --flavor m3.large --num_instances 2")
    result = runner.invoke(vm_group, ['cost', '--flavor', 'm3.large', '--num_instances', '2'])
    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.output}")
    
    # Test 3: Cost command help
    print("\nTesting: cmc vm cost help")
    result = runner.invoke(vm_group, ['cost', 'help'])
    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.output}")

if __name__ == "__main__":
    test_cost_command()
