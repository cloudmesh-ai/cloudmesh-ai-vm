#!/usr/bin/env python3
"""Wrapper forwarding to test-vm-openstack-chameleon.py"""
import runpy
from pathlib import Path

target = Path(__file__).parent / "test-vm-openstack-chameleon.py"
runpy.run_path(str(target), run_name="__main__")
