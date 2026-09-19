from cloudmesh.ai.vm.local.MultipassManager import Provider
from unittest.mock import patch, MagicMock

def test_fix():
    mock_config = {
        "clouds": {
            "multipass": {
                "image": "22.04",
                "cpus": 2,
                "memory": "4GiB",
                "disk": "20GiB"
            }
        }
    }
    provider = Provider(mock_config)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="Success", returncode=0)
        # Use a patch for _run_command since that's what MultipassManager uses
        with patch.object(provider, "_run_command") as mock_run_cmd:
            result = provider.start(name="test-vm")
            print(f"Result: {result}")
            assert result == "test-vm"
            print("Test passed!")

if __name__ == "__main__":
    try:
        test_fix()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
