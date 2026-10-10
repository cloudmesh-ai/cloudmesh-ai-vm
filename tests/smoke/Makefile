# Makefile for VM Smoke Tests
# Use this to run specific provider smoke tests easily.

.PHONY: all multipass lima chameleon jetstream vbox wsl2 clean

# Default target: run all smoke tests
all:
	python3 -m pytest -s -vv tests/smoke

# Run Multipass smoke tests
multipass:
	OS_CLOUD=multipass python3 -m pytest -s -vv test_cli_multipass.py test_multipass_smoke.py

# Run Lima smoke tests
lima:
	OS_CLOUD=lima python3 -m pytest -s -vv test_cli_lima.py test_lima_smoke.py

# Run Chameleon smoke tests
chameleon:
	OS_CLOUD=chameleon python3 -m pytest -s -vv test_cli_chameleon.py

# Run Jetstream smoke tests
jetstream:
	OS_CLOUD=jetstream python3 -m pytest -s -vv test_cli_jetstream.py test_jetstream_smoke.py

# Run VirtualBox smoke tests
vbox:
	OS_CLOUD=vbox python3 -m pytest -s -vv test_vbox_smoke.py

# Run WSL2 smoke tests
wsl2:
	OS_CLOUD=wsl2 python3 -m pytest -s -vv test_wsl2_smoke.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
