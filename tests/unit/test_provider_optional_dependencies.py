import subprocess
import sys


def test_lima_available_without_chameleon_dependency():
    """Lima provider discovery must not require python-chi."""
    script = """
import builtins

original_import = builtins.__import__

def block_chi(name, *args, **kwargs):
    if name == "chi" or name.startswith("chi."):
        raise ModuleNotFoundError("No module named 'chi'", name="chi")
    return original_import(name, *args, **kwargs)

builtins.__import__ = block_chi

from cloudmesh.ai.vm.providers import PROVIDER_MAP, get_provider_classes

assert "lima" in PROVIDER_MAP
assert "lima" in get_provider_classes()
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        f"Provider discovery failed:\n{result.stdout}\n{result.stderr}"
    )
