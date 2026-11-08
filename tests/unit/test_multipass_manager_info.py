"""Unit tests for the ``info`` method of the Multipass provider.

These tests verify that the method parses both JSON and plain‑text output from
``multipass info`` into a structured dictionary.  The provider is instantiated
with a minimal mock configuration and its ``_run_command`` method is stubbed
out to avoid invoking the real ``multipass`` binary.
"""

from unittest.mock import MagicMock

import pytest

from cloudmesh.ai.vm.local.MultipassManager import Provider


@pytest.fixture
def mock_config():
    """Return a minimal configuration dictionary for Multipass.

    The configuration mirrors the structure used throughout the test suite –
    only the fields required by the provider are included.
    """
    return {
        "clouds": {
            "multipass": {
                "image": "22.04",
                "cpus": 2,
                "memory": "4GiB",
                "disk": "20GiB",
            }
        }
    }


@pytest.fixture
def provider(mock_config):
    """Create a :class:`MultipassManager.Provider` with a mocked ``_run_command``.

    The ``_run_command`` attribute will be replaced in each test to return the
    appropriate stdout payload for the scenario under test.
    """
    p = Provider(mock_config)
    # ``exists`` checks are performed before calling ``info`` – monkey‑patch to
    # always report that the VM exists.
    p.exists = MagicMock(return_value=True)
    return p


def test_info_parses_json_output(provider):
    """When ``multipass info`` returns JSON, the method should return a flat dict.

    The expected dictionary contains the VM ``name`` as a top‑level key, a
    ``status`` field derived from the JSON ``state`` entry, the first IPv4 in
    ``ip`` as well as the raw ``ipv4`` list, and preserves all other metadata.
    """
    json_output = (
        '{'
        '    "info": {'
        '        "test-vm": {'
        '            "state": "Running", '
        '            "ipv4": ["10.0.2.15"], '
        '            "release": "22.04 LTS", '
        '            "image_hash": "abcdef"'
        '        }'
        '    }'
        '}'
    )
    # Mock the command execution to return the JSON payload.
    provider._run_command = MagicMock(return_value=MagicMock(stdout=json_output, returncode=0))

    info = provider.info(name="test-vm")

    # Basic structural expectations.
    assert isinstance(info, dict)
    assert info["name"] == "test-vm"
    # ``status`` is derived from ``state``.
    assert info["status"] == "Running"
    # Capitalised alias for backwards compatibility.
    assert info["State"] == "Running"
    # IPv4 handling – both the raw list and the convenience field.
    assert info["ipv4"] == ["10.0.2.15"]
    assert info["ip"] == "10.0.2.15"
    # Additional metadata should be present unchanged.
    assert info["release"] == "22.04 LTS"
    assert info["image_hash"] == "abcdef"


def test_info_fallback_to_text_parsing(provider):
    """If JSON parsing fails, ``info`` should gracefully parse the human‑readable output.

    The fallback parser lower‑cases keys and extracts the first IPv4 address.
    """
    text_output = (
        "Name:           test-vm\n"
        "State:          Stopped\n"
        "IPv4:           10.1.2.3 10.2.3.4\n"
        "Release:        22.04 LTS\n"
    )
    provider._run_command = MagicMock(return_value=MagicMock(stdout=text_output, returncode=0))

    info = provider.info(name="test-vm")

    assert isinstance(info, dict)
    # The provider adds a lower‑case ``name`` entry in both parsers.
    assert info["name"] == "test-vm"
    # Text parser lower‑cases the key to ``state``.
    assert info["state"] == "Stopped"
    # Compatibility alias ``State`` should also be present.
    assert info["State"] == "Stopped"
    # IPv4 handling – ensure both the list and the first entry are captured.
    assert info["ipv4"] == ["10.1.2.3", "10.2.3.4"]
    assert info["ip"] == "10.1.2.3"
    assert info["release"] == "22.04 LTS"