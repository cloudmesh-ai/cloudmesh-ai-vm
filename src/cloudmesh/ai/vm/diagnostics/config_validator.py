"""Configuration validation utilities for the ``cmx vm doctor`` command.

This module implements the same exhaustive checks that are performed by the
smoke test ``tests/smoke/test_config.py`` but returns the results in a format
that can be consumed by the ``doctor`` CLI.  The goal is to provide a single
source of truth for configuration validation so that both the test suite and
the user‑facing ``doctor`` command stay in sync.

The API mirrors the plan outlined in ``plan-doctor.md``:

* ``_load_yaml`` – Load a YAML file and return a ``(data, error)`` tuple.
* ``validate_cloudmesh_config`` – Run all Cloudmesh‑specific checks.
* ``validate_openstack_config`` – Run all OpenStack‑specific checks.
* ``run_all_config_checks`` – Aggregate the two dictionaries above.

All functions return a mapping of *check name* → ``(status, details)`` where
``status`` is one of ``"PASS"``, ``"FAIL"`` or ``"WARN"``.  ``details`` is a
human‑readable string that will be displayed as the ``Details`` column in the
doctor table.
"""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Dict, Tuple, List, Optional

# Default configuration file locations – these are the same locations used by
# the existing ``tests/smoke/test_config.py`` smoke test.
CLOUDMESH_PATH = os.path.expanduser("~/.config/cloudmesh/clouds.yaml")
OPENSTACK_PATH = os.path.expanduser("~/.config/openstack/clouds.yaml")


def _load_yaml(path: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Load a YAML file, returning ``(data, error_message)``.

    ``data`` is a ``dict`` when parsing succeeds; ``None`` otherwise.
    ``error_message`` is ``None`` on success and a human‑readable message on
    failure (missing file, parse error, or unexpected root type).
    """
    if not os.path.isfile(path):
        return None, f"Configuration file not found: {path}"

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        # Extract line/column information similarly to the smoke test.
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
        line_msg = f"line {line + 1}" if line is not None else "unknown line"
        col_msg = f"column {column + 1}" if column is not None else "unknown column"
        return (
            None,
            f"Invalid YAML in {path}: ({line_msg}, {col_msg}, attribute '{attribute}')",
        )
    except Exception as e:  # pragma: no cover – unexpected I/O errors
        return None, f"Error reading {path}: {e}"

    if not isinstance(data, dict):
        return None, f"Root of {path} must be a mapping"
    return data, None


# ---------------------------------------------------------------------------
# Cloudmesh configuration validation
# ---------------------------------------------------------------------------

def _validate_cloudmesh_provider_keys(
    clouds: Dict, provider: str, required_keys: List[str]
) -> Tuple[str, str]:
    """Validate required keys for a specific Cloudmesh provider.

    Returns a ``(status, details)`` tuple.  ``status`` follows the ``PASS``/``FAIL``
    convention used throughout the doctor command.
    """
    cfg = clouds.get(provider)
    if cfg is None:
        # Provider not present – not an error for the validator (the provider is
        # optional for a given installation).
        return "PASS", f"Provider '{provider}' not configured (optional)."
    missing = [k for k in required_keys if k not in cfg]
    if missing:
        return (
            "FAIL",
            f"Missing required fields for provider '{provider}': {', '.join(missing)}",
        )
    return "PASS", f"All required keys for provider '{provider}' are present."


def validate_cloudmesh_config() -> Dict[str, Tuple[str, str]]:
    """Validate the Cloudmesh configuration file.

    Returns a mapping from a human readable check name to a ``(status, details)``
    pair.  The checks roughly correspond to the individual tests in
    ``tests/smoke/test_config.py``.
    """
    results: Dict[str, Tuple[str, str]] = {}

    # 1. File existence
    if not os.path.isfile(CLOUDMESH_PATH):
        results["File existence"] = (
            "FAIL",
            f"Configuration file not found: {CLOUDMESH_PATH}",
        )
        # Without a file we cannot continue with deeper checks.
        return results
    results["File existence"] = ("PASS", f"Found configuration at {CLOUDMESH_PATH}")

    # 2. YAML parsing
    cfg, error = _load_yaml(CLOUDMESH_PATH)
    if error:
        results["YAML parsing"] = ("FAIL", error)
        return results
    results["YAML parsing"] = ("PASS", "YAML parsed successfully")

    # 3. Top‑level ``username``
    username = cfg.get("username") if cfg else None
    if username is None or not str(username).strip():
        results["Username exists"] = (
            "FAIL",
            "Missing or empty top‑level 'username' key",
        )
    else:
        results["Username exists"] = ("PASS", f"Username '{username}' is set")

    # 4. ``clouds`` mapping
    clouds = cfg.get("clouds") if cfg else None
    if not isinstance(clouds, dict):
        results["Clouds mapping"] = (
            "FAIL",
            "Missing or invalid 'clouds' mapping in Cloudmesh config",
        )
        return results
    results["Clouds mapping"] = ("PASS", "'clouds' mapping present")

    # 5. Provider‑specific required keys
    provider_requirements: Dict[str, List[str]] = {
        "multipass": ["enabled", "image", "name"],
        "lima": ["enabled", "name", "template"],
        "jetstream": ["enabled", "flavor", "image", "key_path", "name"],
        "chameleon": ["enabled", "flavor", "image", "key_path", "name"],
    }
    for prov, req_keys in provider_requirements.items():
        status, details = _validate_cloudmesh_provider_keys(clouds, prov, req_keys)
        results[f"Provider {prov} required keys"] = (status, details)

    # 6. Chameleon region validation (optional provider specific rule)
    ch_cfg = clouds.get("chameleon")
    if ch_cfg is not None:
        if "region" not in ch_cfg and "region_name" not in ch_cfg:
            results["Chameleon region"] = (
                "FAIL",
                "Chameleon configuration must contain a 'region' or 'region_name' key",
            )
        else:
            results["Chameleon region"] = ("PASS", "Region information present")

    return results


# ---------------------------------------------------------------------------
# OpenStack configuration validation
# ---------------------------------------------------------------------------

def _assert_openstack_provider_structure(
    provider_name: str, provider_cfg: Dict
) -> List[str]:
    """Validate a single OpenStack provider configuration.

    Returns a list of error strings – empty when the provider configuration is
    valid.
    """
    errors: List[str] = []
    top_keys = ["auth", "region_name", "interface", "identity_api_version", "auth_type"]
    missing_top = [k for k in top_keys if k not in provider_cfg]
    if missing_top:
        errors.append(
            f"Provider '{provider_name}' missing keys: {', '.join(missing_top)}"
        )
        return errors

    auth_cfg = provider_cfg.get("auth")
    if not isinstance(auth_cfg, dict):
        errors.append(f"Provider '{provider_name}' auth must be a mapping")
        return errors
    auth_keys = ["auth_url", "application_credential_id", "application_credential_secret"]
    missing_auth = [k for k in auth_keys if k not in auth_cfg]
    if missing_auth:
        errors.append(
            f"Provider '{provider_name}' auth missing keys: {', '.join(missing_auth)}"
        )
        return errors
    # Validate that values are non‑empty strings (or numeric for version).
    for k in auth_keys:
        val = auth_cfg.get(k)
        if val is None or not isinstance(val, str) or not val.strip():
            errors.append(
                f"Provider '{provider_name}' auth key '{k}' must be a non‑empty string"
            )
    for k in ["region_name", "interface", "auth_type"]:
        val = provider_cfg.get(k)
        if val is None or not isinstance(val, str) or not val.strip():
            errors.append(
                f"Provider '{provider_name}' key '{k}' must be a non‑empty string"
            )
    # identity_api_version: allow int > 0 or numeric string
    id_val = provider_cfg.get("identity_api_version")
    if isinstance(id_val, int):
        if id_val <= 0:
            errors.append(
                f"Provider '{provider_name}' identity_api_version must be positive"
            )
    elif isinstance(id_val, str):
        if not id_val.isdigit():
            errors.append(
                f"Provider '{provider_name}' identity_api_version must be numeric"
            )
    else:
        errors.append(
            f"Provider '{provider_name}' identity_api_version must be int or numeric string"
        )
    return errors


def validate_openstack_config() -> Dict[str, Tuple[str, str]]:
    """Validate the OpenStack configuration file.

    Returns a mapping from check name to ``(status, details)``.  The checks are
    analogous to those performed by the smoke test.
    """
    results: Dict[str, Tuple[str, str]] = {}

    # 1. File existence
    if not os.path.isfile(OPENSTACK_PATH):
        results["File existence"] = (
            "FAIL",
            f"Configuration file not found: {OPENSTACK_PATH}",
        )
        return results
    results["File existence"] = ("PASS", f"Found configuration at {OPENSTACK_PATH}")

    # 2. YAML parsing
    cfg, error = _load_yaml(OPENSTACK_PATH)
    if error:
        results["YAML parsing"] = ("FAIL", error)
        return results
    results["YAML parsing"] = ("PASS", "YAML parsed successfully")

    clouds = cfg.get("clouds") if cfg else None
    if not isinstance(clouds, dict):
        results["Clouds mapping"] = (
            "FAIL",
            "Missing or invalid 'clouds' mapping in OpenStack config",
        )
        return results
    results["Clouds mapping"] = ("PASS", "'clouds' mapping present")

    # 3. Provider structure validation
    all_errors: List[str] = []
    for name, provider_cfg in clouds.items():
        if not isinstance(provider_cfg, dict):
            all_errors.append(
                f"Provider '{name}' configuration must be a mapping"
            )
            continue
        provider_errors = _assert_openstack_provider_structure(name, provider_cfg)
        all_errors.extend(provider_errors)

    if all_errors:
        results["Provider structure"] = ("FAIL", "; ".join(all_errors))
    else:
        results["Provider structure"] = ("PASS", "All providers have required structure")

    return results


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

def run_all_config_checks() -> Dict[str, Dict[str, Tuple[str, str]]]:
    """Run both Cloudmesh and OpenStack configuration checks.

    The return value is a nested dictionary mapping a top‑level section name
    (``"Cloudmesh Config"`` or ``"OpenStack Config"``) to the per‑check result
    dictionary produced by the corresponding validator.
    """
    return {
        "Cloudmesh Config": validate_cloudmesh_config(),
        "OpenStack Config": validate_openstack_config(),
    }
