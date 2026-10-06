import shutil
import pytest
from cloudmesh.ai.vm.local.Wsl2Manager import Provider

@pytest.fixture
def provider():
    if shutil.which("wsl.exe") is None:
        pytest.skip("wsl.exe is not available in this environment")

    return Provider({
        "clouds": {
            "wsl2": {
                "wsl_username": "root"
            }
        }
    })

@pytest.fixture
def distro(provider):
    distributions = provider.list()
    if not distributions:
        pytest.skip("No WSL2 distributions are installed")
    return distributions[0]["Name"]

def test_wsl2_requirements_detect_real_cli(provider):
    assert provider.check_requirements() is True

def test_wsl2_list_real_distributions(provider):
    distributions = provider.list()
    assert distributions
    for vm in distributions:
        assert vm["Name"]
        assert vm["State"]
        assert vm["Version"]

def test_wsl2_exists_real_and_missing_distribution(provider, distro):
    assert provider.exists(distro) is True
    assert provider.exists("cloudmesh-does-not-exist") is False

def test_wsl2_info_real_distribution(provider, distro):
    info = provider.info(distro)
    assert "RawInfo" in info
    assert distro in info["RawInfo"]

def test_wsl2_version_real_cli(provider):
    versions = provider.version
    assert versions
    assert versions != ["Unknown"]
    assert any("WSL version:" in line for line in versions)

def test_wsl2_run_command_real_distribution(provider, distro):
    output = provider.run_command(distro, "printf cloudmesh-wsl2-test")
    assert output == "cloudmesh-wsl2-test"

def test_wsl2_info_missing_distribution_raises(provider):
    from cloudmesh.ai.vm.exceptions import VMResourceError
    with pytest.raises(VMResourceError, match="Distribution cloudmesh-does-not-exist not found"):
        provider.info("cloudmesh-does-not-exist")

def test_wsl2_run_command_missing_distribution_raises(provider):
    from cloudmesh.ai.vm.exceptions import VMProviderError
    with pytest.raises(VMProviderError, match="VM cloudmesh-does-not-exist not found"):
        provider.run_command("cloudmesh-does-not-exist", "printf test")

def test_wsl2_get_provider_info_real_cli(provider):
    info = provider.get_provider_info()
    assert info["provider"] == "WSL2"
    assert info["cloud_name"] == "wsl2"
    assert isinstance(info["version"], list)
    assert info["version"]

def test_wsl2_wait_for_running_status_real_distribution(provider, distro):
    assert provider.wait_for_status(
        distro,
        "Running",
        timeout=10,
    ) is True
