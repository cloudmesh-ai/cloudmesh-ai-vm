"""Test that ensures the repository is run with a supported minimum Python version.

The project targets **Python 3.15.2** as the minimum required interpreter.
Running the test suite on an older interpreter will cause this test to
fail, alerting developers and CI that the Python version needs to be
updated.
"""

import sys


def test_minimum_python_version() -> None:
    """Assert the running interpreter is at least Python 3.15.2.

    The test deliberately uses a plain ``assert`` so that it fails (instead
    of being x‑failed) when the version is too old.  CI should therefore
    break until the required version is used.
    """
    major, minor, micro = sys.version_info[:3]
    assert (major, minor, micro) >= (3, 15, 2), (
        f"Python >=3.15.2 required, got {major}.{minor}.{micro}"
    )
