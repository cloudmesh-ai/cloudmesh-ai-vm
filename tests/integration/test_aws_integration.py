import pytest


def test_aws_lifecycle(get_provider):
    """
    Full lifecycle test for AWS: Start -> Info -> Stop -> Delete.
    Skips if AWS credentials are not configured.
    """
    try:
        provider = get_provider("aws")
    except Exception as e:
        pytest.skip(f"AWS credentials not configured or provider error: {e}")

    vm_name = "integration-test-aws-vm"

    try:
        # 1. Start VM
        print(f"Launching AWS VM {vm_name}...")
        vm_id = provider.start(name=vm_name)
        assert vm_id is not None

        # 2. Verify Info
        print(f"Fetching info for {vm_name}...")
        info = provider.info(vm_id)
        assert info["Name"] == vm_name

        # 3. Stop VM
        print(f"Stopping AWS VM {vm_name}...")
        assert provider.stop(vm_id) is True

        # 4. Delete VM
        print(f"Deleting AWS VM {vm_name}...")
        assert provider.delete(vm_id) is True

    finally:
        # Final cleanup attempt
        try:
            provider.delete(vm_name)
        except Exception:
            pass
