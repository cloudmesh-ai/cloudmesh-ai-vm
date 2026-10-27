import json
import uuid
import pytest
from click.testing import CliRunner
from rich.text import Text
from cloudmesh.ai.common.stopwatch import StopWatch

from cloudmesh.ai.command import container
from tests.smoke.benchmark_helper import (
    create_benchmark_payload,
    get_results_username,
    save_benchmark,
)
from tests.smoke.cli_helper import setup_cli_config

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def config(tmp_path, runner):
    provider_config = {
        "image": "ubuntu:latest",
    }
    setup_cli_config(tmp_path, "docker", provider_config)

@pytest.fixture(scope="module")
def docker_container_name():
    """
    Generates a consistent container name for the test module to prevent leaking containers.
    """
    import yaml
    import os
    
    config_path = os.path.expanduser("~/.config/cloudmesh/clouds.yaml")
    username = "smoke-user"
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
                username = data.get("clouds", {}).get("docker", {}).get("username", "smoke-user")
    except Exception:
        pass

    short_uuid = str(uuid.uuid4())[:5]
    return f"cloudmesh-docker-{username}-{short_uuid}"

def test_docker_cli_lifecycle(runner, config, docker_container_name):
    """
    Smoke test for Docker CLI lifecycle.
    """
    env = {"OS_CLOUD": "docker"}
    container_name = docker_container_name

    # Pre-cleanup: Ensure no stale container exists with this name
    runner.invoke(container.container_group, ["delete", container_name], env=env)

    # 1. Run (Create & Start)
    with StopWatch.timer("run"):
        result = runner.invoke(container.container_group, ["run", "--name", container_name, "--image", "alpine", "sleep", "3600"], env=env)
    StopWatch.status("run", result.exit_code == 0)
    output = Text.from_ansi(result.output).plain
    
    try:
        assert result.exit_code == 0, f"Docker run failed: {output}"
        assert f"Container {container_name} created and started" in output

        # 2. List
        with StopWatch.timer("list"):
            result = runner.invoke(container.container_group, ["list"], env=env)
        StopWatch.status("list", result.exit_code == 0)
        assert result.exit_code == 0
        plain_output = Text.from_ansi(result.output).plain
        assert container_name in plain_output

        # 3. Info
        with StopWatch.timer("info"):
            result = runner.invoke(container.container_group, ["info", container_name], env=env)
        StopWatch.status("info", result.exit_code == 0)
        assert result.exit_code == 0
        plain_output = Text.from_ansi(result.output).plain
        assert container_name in plain_output

        # 4. IP (New Symmetry Feature)
        with StopWatch.timer("ip"):
            result = runner.invoke(container.container_group, ["ip", "list"], env=env)
        StopWatch.status("ip", result.exit_code == 0)
        assert result.exit_code == 0
        plain_output = Text.from_ansi(result.output).plain
        assert container_name in plain_output

        # 5. Restart (New Symmetry Feature)
        with StopWatch.timer("restart"):
            result = runner.invoke(container.container_group, ["restart", container_name], env=env)
        StopWatch.status("restart", result.exit_code == 0)
        assert result.exit_code == 0
        assert f"Container {container_name} restarted" in Text.from_ansi(result.output).plain

        # 6. Suspend (Pause) (New Symmetry Feature)
        with StopWatch.timer("suspend"):
            result = runner.invoke(container.container_group, ["suspend", "pause", container_name], env=env)
        StopWatch.status("suspend", result.exit_code == 0)
        assert result.exit_code == 0
        assert f"Container {container_name} paused" in Text.from_ansi(result.output).plain

        # 7. Resume (Unpause) (New Symmetry Feature)
        with StopWatch.timer("resume"):
            result = runner.invoke(container.container_group, ["suspend", "resume", container_name], env=env)
        StopWatch.status("resume", result.exit_code == 0)
        assert result.exit_code == 0
        assert f"Container {container_name} resumed" in Text.from_ansi(result.output).plain

        # 8. Image Pull (New Symmetry Feature)
        with StopWatch.timer("image_pull"):
            result = runner.invoke(container.container_group, ["image", "pull", "alpine"], env=env)
        StopWatch.status("image_pull", result.exit_code == 0)
        assert result.exit_code == 0

        # 9. Image List (New Symmetry Feature)
        with StopWatch.timer("image_list"):
            result = runner.invoke(container.container_group, ["image", "list"], env=env)
        StopWatch.status("image_list", result.exit_code == 0)
        assert result.exit_code == 0
        assert "alpine" in Text.from_ansi(result.output).plain

        # 10. Stop
        with StopWatch.timer("stop"):
            result = runner.invoke(container.container_group, ["stop", container_name], env=env)
        StopWatch.status("stop", result.exit_code == 0)
        assert result.exit_code == 0
        assert f"Container {container_name} stopped successfully" in Text.from_ansi(result.output).plain

        # 11. Delete
        with StopWatch.timer("delete"):
            result = runner.invoke(container.container_group, ["delete", container_name], env=env)
        StopWatch.status("delete", result.exit_code == 0)
        assert result.exit_code == 0
        assert f"Container {container_name} deleted successfully" in Text.from_ansi(result.output).plain

    finally:
        # Always attempt to remove the test container
        runner.invoke(container.container_group, ["delete", container_name], env=env)

        # Save standard benchmark text/json files
        save_benchmark(tag="Docker CLI", config_path=config)

        # Retrieve the results username dynamically using the config path
        try:
            username = get_results_username(config_path=config)
        except Exception:
            username = "smoke_test_user"

        # Create and print/save the structured JSON payload
        payload = create_benchmark_payload(benchmark_name="Docker CLI", user=username)
        print(json.dumps(payload, indent=2))
