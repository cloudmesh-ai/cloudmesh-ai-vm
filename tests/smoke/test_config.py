"""Smoke tests for both Cloudmesh and OpenStack configuration files.

The repository ships with example configuration files located at:

* ``~/.config/cloudmesh/clouds.yaml`` – the Cloudmesh configuration used by the
  CLI and the provider factories.
* ``~/.config/openstack/clouds.yaml`` – the OpenStack client configuration that
  tools such as ``openstack`` or ``python-openstackclient`` consume.

These tests verify that **both** files exist, contain valid YAML, and include the
required provider sections with the expected keys.  When a YAML parsing error
occurs, the test reports the line, column, and attribute name that caused the
problem.  No secret values (e.g. application credential secrets) are ever printed;
error messages reference only keys and structural information, with any secret
value represented as ``[masked]`` if it were to be interpolated (the tests avoid
including the value altogether).
"""

import os
from typing import Dict, List

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _load_yaml(path: str) -> Dict:
    """Load a YAML file, raising a helpful ``AssertionError`` on failure.

    The function ensures the file exists, reads it, and parses it with
    ``yaml.safe_load``.  If parsing fails, the raised error includes the line,
    column, and attribute name where the problem was detected (but never the
    offending secret value itself).
    """
    assert os.path.isfile(path), f"Configuration file not found: {path}"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:  # pragma: no cover – exercised only when broken
        # Extract location information if available.
        line = column = None
        attribute = ""
        mark = getattr(e, "problem_mark", None) or getattr(e, "position", None)
        if mark is not None:
            line = getattr(mark, "line", None)
            column = getattr(mark, "column", None)
            if line is not None:
                lines = content.splitlines()
                if 0 <= line < len(lines):
                    raw = lines[line]
                    if ":" in raw:
                        attribute = raw.split(":", 1)[0].strip()
        # Convert to user‑friendly 1‑based line/column numbers.
        line_msg = f"line {line + 1}" if line is not None else "unknown line"
        col_msg = f"column {column + 1}" if column is not None else "unknown column"
        raise AssertionError(
            f"Invalid YAML in {path}: ({line_msg}, {col_msg}, attribute '{attribute}')"
        ) from e
    assert isinstance(data, dict), f"Root of {path} must be a mapping"
    return data


def _assert_provider_keys(provider: str, required: List[str], cfg: Dict) -> None:
    """Assert that *provider* contains all *required* keys with non‑empty values.

    ``cfg`` is the full configuration dictionary (the result of ``_load_yaml``).
    The helper is reused for the Cloudmesh and OpenStack validation.
    """
    clouds = cfg.get("clouds")
    assert isinstance(clouds, dict), "Missing or invalid 'clouds' mapping"
    provider_cfg = clouds.get(provider)
    assert provider_cfg is not None, f"Missing configuration for provider '{provider}'"
    assert isinstance(provider_cfg, dict), f"Provider '{provider}' config must be a mapping"
    for key in required:
        assert key in provider_cfg, f"Missing required key '{key}' for provider '{provider}'"
        val = provider_cfg[key]
        # Ensure the value exists and is not an empty string.
        assert val is not None and str(val).strip() != "", (
            f"Key '{key}' for provider '{provider}' must have a non‑empty value"
        )
        # Path‑like values should expand correctly.
        if key.endswith("_path"):
            expanded = os.path.expanduser(str(val))
            assert isinstance(expanded, str), f"Failed to expand path for '{key}' in provider '{provider}'"


def _assert_openstack_provider_structure(provider_name: str, provider_cfg: Dict) -> None:
    """Validate the expected OpenStack provider structure.

    Required top‑level keys are ``auth``, ``region_name``, ``interface``,
    ``identity_api_version``, and ``auth_type``.  ``auth`` must itself contain
    ``auth_url``, ``application_credential_id``, and ``application_credential_secret``.
    All values must be present and non‑empty but never displayed.
    """
    assert isinstance(provider_cfg, dict), f"Provider '{provider_name}' config must be a mapping"
    top_keys = ["auth", "region_name", "interface", "identity_api_version", "auth_type"]
    for k in top_keys:
        assert k in provider_cfg, f"Missing key '{k}' in OpenStack provider '{provider_name}'"
    auth_cfg = provider_cfg["auth"]
    assert isinstance(auth_cfg, dict), f"'auth' for provider '{provider_name}' must be a mapping"
    auth_keys = ["auth_url", "application_credential_id", "application_credential_secret"]
    for k in auth_keys:
        assert k in auth_cfg, f"Missing auth key '{k}' in OpenStack provider '{provider_name}'"
        val = auth_cfg[k]
        assert val is not None and str(val).strip() != "", (
            f"Auth key '{k}' for provider '{provider_name}' must have a non‑empty value"
        )


# ---------------------------------------------------------------------------
# Cloudmesh configuration tests
# ---------------------------------------------------------------------------

CLOUDMESH_PATH = os.path.expanduser("~/.config/cloudmesh/clouds.yaml")


def test_cloudmesh_config_exists():
    """Assert that the Cloudmesh configuration file is present."""
    assert os.path.isfile(CLOUDMESH_PATH), f"Cloudmesh config not found at {CLOUDMESH_PATH}"


def test_cloudmesh_yaml_is_valid():
    """Load the Cloudmesh YAML and ensure it parses without errors."""
    _ = _load_yaml(CLOUDMESH_PATH)


def test_cloudmesh_username_exists():
    """Ensure the Cloudmesh configuration includes a top‑level ``username``.

    The ``username`` key is used throughout the VM management commands to
    generate unique VM names and for logging.  It must be present and have a
    non‑empty value.
    """
    cfg = _load_yaml(CLOUDMESH_PATH)
    assert "username" in cfg, "Cloudmesh config must contain a top‑level 'username' key"
    val = cfg["username"]
    assert val is not None and str(val).strip() != "", "The 'username' value in Cloudmesh config must be non‑empty"


@pytest.mark.parametrize(
    "provider,required",
    [
        ("multipass", ["enabled", "image", "name"]),
        ("lima", ["enabled", "name", "template"]),
        ("jetstream", ["enabled", "flavor", "image", "key_path", "name"]),
        ("chameleon", ["enabled", "flavor", "image", "key_path", "name"]),
    ],
)
def test_cloudmesh_provider_keys(provider: str, required: List[str]):
    """Check that each required Cloudmesh provider contains the mandatory keys."""
    cfg = _load_yaml(CLOUDMESH_PATH)
    _assert_provider_keys(provider, required, cfg)


def test_cloudmesh_chameleon_region():
    """Chameleon provider must specify a region (either ``region`` or ``region_name``)."""
    cfg = _load_yaml(CLOUDMESH_PATH)
    clouds = cfg.get("clouds")
    assert isinstance(clouds, dict)
    ch_cfg = clouds.get("chameleon")
    assert ch_cfg is not None
    has_region = "region" in ch_cfg or "region_name" in ch_cfg
    assert has_region, "Chameleon configuration must contain a 'region' or 'region_name' key"

# ---------------------------------------------------------------------------
# OpenStack configuration tests
# ---------------------------------------------------------------------------

OPENSTACK_PATH = os.path.expanduser("~/.config/openstack/clouds.yaml")


def test_openstack_config_exists():
    """Assert that the OpenStack configuration file is present."""
    assert os.path.isfile(OPENSTACK_PATH), f"OpenStack config not found at {OPENSTACK_PATH}"


def test_openstack_yaml_is_valid():
    """Load the OpenStack YAML and ensure it parses without errors."""
    _ = _load_yaml(OPENSTACK_PATH)


def test_openstack_provider_structure():
    """Validate the structure of each provider block in the OpenStack config.

    The test iterates over all providers defined under the top‑level ``clouds``
    key and checks that each contains the mandatory authentication fields.
    """
    cfg = _load_yaml(OPENSTACK_PATH)
    clouds = cfg.get("clouds")
    assert isinstance(clouds, dict), "Missing or invalid 'clouds' mapping in OpenStack config"
    for name, provider_cfg in clouds.items():
        _assert_openstack_provider_structure(name, provider_cfg)


def test_openstack_jetstream_format():
    """Validate that the Jetstream entry in the OpenStack config follows the
    expected schema.

    The required structure is:

    ::

        auth:
          auth_url: <str>
          application_credential_id: <str>
          application_credential_secret: <str>
        region_name: <str>
        interface: <str>
        identity_api_version: <int|str>
        auth_type: <str>

    All values must be non‑empty strings (or an integer for ``identity_api_version``).
    Secret values are not printed; we only ensure that they exist and are non‑empty.
    """
    cfg = _load_yaml(OPENSTACK_PATH)
    clouds = cfg.get("clouds")
    assert isinstance(clouds, dict), "Missing or invalid 'clouds' mapping in OpenStack config"
    jet = clouds.get("jetstream")
    assert jet is not None, "OpenStack config must contain a 'jetstream' provider"
    # Top‑level keys
    top_keys = ["auth", "region_name", "interface", "identity_api_version", "auth_type"]
    for key in top_keys:
        assert key in jet, f"Jetstream config missing required key '{key}'"
    # Validate auth sub‑keys
    auth = jet["auth"]
    assert isinstance(auth, dict), "Jetstream 'auth' must be a mapping"
    auth_keys = ["auth_url", "application_credential_id", "application_credential_secret"]
    for key in auth_keys:
        assert key in auth, f"Jetstream auth missing required key '{key}'"
        val = auth[key]
        assert isinstance(val, str) and val.strip(), f"Jetstream auth key '{key}' must be a non‑empty string"
    # Validate other fields are non‑empty strings (or int for identity_api_version)
    for key in ["region_name", "interface", "auth_type"]:
        val = jet[key]
        assert isinstance(val, str) and val.strip(), f"Jetstream key '{key}' must be a non‑empty string"
    # identity_api_version can be int or string representing an int
    identity_val = jet["identity_api_version"]
    # Accept int or numeric string
    if isinstance(identity_val, int):
        assert identity_val > 0, "identity_api_version must be a positive integer"
    else:
        assert isinstance(identity_val, str) and identity_val.isdigit(), (
            "identity_api_version must be an integer or numeric string"
        )


def test_openstack_chameleon_format():
    """Validate the Chameleon entry in the OpenStack clouds.yaml.

    Expected structure (all values must be non‑empty):

    ::

        chameleon:
          auth:
            auth_url: <str>
            application_credential_id: <str>
            application_credential_secret: <str>
          region_name: <str>
          interface: <str>
          identity_api_version: <int|str>
          auth_type: <str>
    """
    cfg = _load_yaml(OPENSTACK_PATH)
    clouds = cfg.get("clouds")
    assert isinstance(clouds, dict), "Missing or invalid 'clouds' mapping in OpenStack config"
    ch = clouds.get("chameleon")
    assert ch is not None, "OpenStack config must contain a 'chameleon' provider"
    # Verify required top‑level keys
    top_keys = ["auth", "region_name", "interface", "identity_api_version", "auth_type"]
    for key in top_keys:
        assert key in ch, f"Chameleon config missing required key '{key}'"
    # Validate auth sub‑keys
    auth = ch["auth"]
    assert isinstance(auth, dict), "Chameleon 'auth' must be a mapping"
    auth_keys = ["auth_url", "application_credential_id", "application_credential_secret"]
    for key in auth_keys:
        assert key in auth, f"Chameleon auth missing required key '{key}'"
        val = auth[key]
        assert isinstance(val, str) and val.strip(), f"Chameleon auth key '{key}' must be a non‑empty string"
    # Validate remaining fields are non‑empty strings (or int for identity_api_version)
    for key in ["region_name", "interface", "auth_type"]:
        val = ch[key]
        assert isinstance(val, str) and val.strip(), f"Chameleon key '{key}' must be a non‑empty string"
    # identity_api_version can be int or numeric string
    identity_val = ch["identity_api_version"]
    if isinstance(identity_val, int):
        assert identity_val > 0, "identity_api_version must be a positive integer"
    else:
        assert isinstance(identity_val, str) and identity_val.isdigit(), (
            "identity_api_version must be an integer or numeric string"
        )
