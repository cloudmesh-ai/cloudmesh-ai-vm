import json
import os
import platform  # these need to be removes and sysinfo needs to be used
import subprocess
import sys  # these need to be removes and sysinfo needs to be used
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO

import yaml
from cloudmesh.ai.common.stopwatch import StopWatch
from cloudmesh.ai.common.sys import systeminfo

# Git info


def get_git_info():
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True
        ).strip()
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
        git_info = f"Branch: {branch}\nCommit: {commit}"
        git_data = {"branch": branch, "commit": commit}
    except Exception:
        git_info = "Git info unavailable"
        git_data = {}
    return git_info, git_data


def get_results_username(config_path: str | None = None) -> str:
    """
    Determines the username for result filenames.
    Only uses ~/.config/cloudmesh/clouds.yaml.
    If not found, raises a RuntimeError asking the user to set it.
    """
    # Try ~/.config/cloudmesh/clouds.yaml
    global_config_path = os.path.expanduser("~/.config/cloudmesh/clouds.yaml")
    try:
        if os.path.exists(global_config_path):
            with open(global_config_path, "r") as cf:
                config = yaml.safe_load(cf)
                if config and isinstance(config, dict):
                    username = config.get("username")
                    if username:
                        return username.replace("cloudmesh-", "")
    except Exception:
        pass

    # No fallback to config_path or 'unknown-user' as per user request
    raise RuntimeError(
        "Username is missing from the global configuration file ~/.config/cloudmesh/clouds.yaml. "
        "Please set the 'username' field in the YAML file to run benchmarks."
    )


def create_benchmark_payload(benchmark_name: str, user: str = "gregor") -> dict:

    # Git info
    _git_info, git_data = get_git_info()

    # Example usage:
    # payload = create_benchmark_payload("lima-smoke",
    #                                     branch="main",
    #                                     commit="39ba1872...")
    # print(json.dumps(payload, indent=2))

    # 1. Gather experiment metadata

    experiment_data = {
        "benchmark": benchmark_name,
        "date": datetime.now().isoformat(),
        "user": user,
        "branch": git_data.get("branch", "unknown-branch"),
        "commit": git_data.get("commit", "unknown-commit"),
    }

    # 2. Gather system / runtime information (omitting hardware block)
    system_data = {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "node": platform.node(),
            "platform_version": platform.mac_ver()[0]
            if platform.system() == "Darwin"
            else platform.version(),
            "sys_platform": sys.platform,
            "python": sys.version,
            "python_version": platform.python_version(),
            "python_pip": getattr(
                sys, "pypy_version_info", None
            ),  # Or fallback pip version check if needed
        },
    }

    # 3. Extract active timers from Stopwatch
    timers_list = []
    # Stopwatch typically stores completed timers in a dictionary or accessible attribute
    # For each timer recorded via Stopwatch:
    for name in StopWatch.keys():
        # Gather the individual pieces from the public API
        status = StopWatch.get_status(name)
        # Turn the internal boolean/None into a readable string (matches the output format of benchmark())
        status_str = (
            "ok" if status is True else ("failed" if status is False else "unknown")
        )
        # Elapsed time for the *last* start/stop pair
        elapsed = StopWatch.get(name)  # may be float or "undefined"
        # Total summed time (if the timer was started/stopped multiple times)
        total = StopWatch.sum(name)  # may be float or "undefined"
        # Optional message attached with StopWatch.message()
        msg = StopWatch.get_message(name)

        timers_list.append(
            {
                "name": name,
                "status": status_str,
                "time": float(elapsed) if isinstance(elapsed, float) else None,
                "sum": float(total) if isinstance(total, float) else None,
                "msg": msg,
            }
        )

    # 4. Construct final root dictionary
    payload = {
        "experiment": experiment_data,
        "system": system_data,
        "timers": timers_list,
    }

    return payload


def save_benchmark(tag, config_path):
    """
    Captures the output of StopWatch.benchmark and saves it to a file in the results directory.
    """

    # 1. Collect Metadata
    # Username from config
    username = get_results_username(config_path)

    # Capture the benchmark output
    f = StringIO()
    with redirect_stdout(f):
        # Call systeminfo before benchmark and set user=results_username
        import yaml

        print(yaml.dump(systeminfo(user=username), default_flow_style=False))
        # Call benchmark without a tag to collect all recorded timers for this session
        StopWatch.benchmark(sysinfo=False)
    benchmark_output = f.getvalue()

    # Git info
    git_info, git_data = get_git_info()
    git_data.get("branch", "unknown-branch")

    # Date and Time
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M:%S")
    date_short = now.strftime("%Y-%m-%d")
    time_short = now.strftime("%H-%M")

    # 3. Write to file
    # Ensure results are saved to the project root's results/smoke directory
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    results_dir = os.path.join(base_dir, "results", "smoke")
    os.makedirs(results_dir, exist_ok=True)

    # Sanitize tag for filename (use - instead of _ to match requested example)
    safe_tag = tag.replace(" ", "-").replace("/", "-").replace(":", "-")

    # Use a timestamp to ensure unique files, but place it before the username/date
    # to ensure the filename ends with -<username>-<date>
    now.strftime("%H%M%S")

    # Format: <safe_tag>-<username>-<date>--<time>
    # This ensures it ends with -<username>-<date>--<time> as requested
    filename_base = f"{safe_tag}-{username}-{date_short}--{time_short}".lower()

    # Text version
    txt_filename = f"{filename_base}.txt"
    txt_file_path = os.path.join(results_dir, txt_filename)
    with open(txt_file_path, "w") as rf:
        rf.write(f"Benchmark: {tag}\n")
        rf.write(f"Date: {date_str}\n")
        rf.write(f"User: {username}\n")
        rf.write(f"{git_info}\n")
        rf.write("-" * 40 + "\n")
        rf.write(benchmark_output)

    # JSON version
    json_filename = f"{filename_base}.json"
    json_file_path = os.path.join(results_dir, json_filename)

    results_data = create_benchmark_payload(benchmark_name=tag, user=username)

    with open(json_file_path, "w") as jf:
        json.dump(results_data, jf, indent=4)

    print(f"Benchmark saved to {txt_file_path} and {json_file_path}")
