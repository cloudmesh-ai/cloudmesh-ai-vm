#!/usr/bin/env bash
# Sydel Ugwu
# Disposable Multipass verification. Run from the cloudmesh-ai-vm checkout.
set -uo pipefail

PYTHON="${PYTHON:-python3}"
for dependency in cmx multipass "$PYTHON"; do
    command -v "$dependency" >/dev/null || { echo "Missing command: $dependency"; exit 2; }
done

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/cmx-week5.XXXXXX")" || exit 2
VM_PREFIX="sugwu-week5-$(date +%s)-$$"
EXPLICIT_VM="${VM_PREFIX}-custom"
export CLOUDMESH_VM_CONFIG="${WORK_DIR}/clouds.yaml"
PASSED=0
FAILED=0
CREATED=()

cleanup() {
    local status="$?"
    trap - EXIT
    if [ -n "${CREATED[0]-}" ]; then
        if multipass list --format json >"${WORK_DIR}/cleanup.json" &&
            "$PYTHON" - "${WORK_DIR}/cleanup.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
assert not any(data.get("errors", [])), data.get("errors")
assert isinstance(data.get("list"), list), "Invalid cleanup inventory"
PY
        then
            for name in "${CREATED[@]}"; do
                if "$PYTHON" - "${WORK_DIR}/cleanup.json" "$name" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
if any(data.get("errors", [])):
    sys.exit(2)
sys.exit(0 if any(vm["name"] == sys.argv[2] for vm in data["list"]) else 1)
PY
                then
                    echo "Cleaning up dedicated test VM: $name"
                    multipass delete --purge "$name" || status=1
                fi
            done
        else
            echo "Could not inspect cleanup inventory. Dedicated names: ${CREATED[*]}"
            status=1
        fi
    fi
    if [ "$status" -ne 0 ] && [ "$FAILED" -eq 0 ]; then
        FAILED=$((FAILED + 1))
    fi
    printf '\nResults: %s passed, %s failed\n' "$PASSED" "$FAILED"
    rm -rf "$WORK_DIR"
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

check() {
    local label="$1"
    shift
    printf '\nTesting: %s\n' "$label"
    if "$@"; then
        PASSED=$((PASSED + 1))
        echo "PASS: $label"
        return 0
    fi
    FAILED=$((FAILED + 1))
    echo "FAIL: $label"
    return 1
}

cmx_vm() { cmx vm --cloud multipass "$@"; }

assert_counter() {
    "$PYTHON" - "$CLOUDMESH_VM_CONFIG" "$1" <<'PY'
import sys, yaml
data = yaml.safe_load(open(sys.argv[1]))
actual = data.get("counter", 0)
assert actual == int(sys.argv[2]), f"Counter {actual}, expected {sys.argv[2]}"
print(f"Counter confirmed: {actual}")
PY
}

assert_state() {
    multipass info "$1" --format json >"${WORK_DIR}/state.json" || return
    "$PYTHON" - "${WORK_DIR}/state.json" "$1" "$2" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
assert not any(data.get("errors", [])), data.get("errors")
actual = data["info"][sys.argv[2]]["state"]
assert actual.lower() == sys.argv[3].lower(), f"State {actual}, expected {sys.argv[3]}"
print(f"{sys.argv[2]} state confirmed: {actual}")
PY
}

assert_absent() {
    multipass list --format json >"${WORK_DIR}/inventory.json" || return
    "$PYTHON" - "${WORK_DIR}/inventory.json" "$1" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
assert not any(data.get("errors", [])), data.get("errors")
assert all(vm["name"] != sys.argv[2] for vm in data["list"]), "VM still exists"
print(f"Deletion confirmed: {sys.argv[2]}")
PY
}

assert_hostname() {
    local actual
    actual="$(cmx_vm run "$1" hostname)" || return
    [ "$actual" = "$1" ] || { echo "Unexpected hostname: $actual"; return 1; }
    echo "Guest hostname confirmed: $actual"
}

assert_format() {
    local format="$1"
    COLUMNS=240 cmx_vm list vms --format "$format" >"${WORK_DIR}/list-output" || return
    "$PYTHON" - "${WORK_DIR}/list-output" "$format" "$EXPLICIT_VM" <<'PY'
import csv, json, sys, yaml
text = open(sys.argv[1]).read()
kind, name = sys.argv[2:]
if kind == "json":
    records = json.loads(text)
elif kind == "yaml":
    records = yaml.safe_load(text)
elif kind == "csv":
    records = list(csv.DictReader(text.splitlines()))
else:
    assert name in text, "Test VM missing from table"
    print("Table contains the test VM")
    sys.exit()
assert any(vm["name"] == name and vm["status"] == "Running" for vm in records)
print(f"{kind} parsed and contains the running test VM")
PY
}

expect_guest_failure() {
    if cmx_vm run "$EXPLICIT_VM" false; then
        echo "The failing guest command unexpectedly returned success"
        return 1
    fi
    echo "Nonzero guest exit was propagated"
}

expect_unsupported() {
    if cmx_vm "$@" >"${WORK_DIR}/unsupported-output" 2>&1; then
        echo "Expected an unsupported feature error: $*"
        return 1
    fi
    "$PYTHON" - "${WORK_DIR}/unsupported-output" <<'PY'
import sys
text = open(sys.argv[1]).read()
assert "does not support" in text or "not support" in text, text
PY
}

assert_other_vms_unchanged() {
    multipass list --format json >"${WORK_DIR}/after.json" || return
    "$PYTHON" - "${WORK_DIR}/before.json" "${WORK_DIR}/after.json" <<'PY'
import json, sys
before, after = [json.load(open(path)) for path in sys.argv[1:]]
assert not any(before.get("errors", [])) and not any(after.get("errors", []))
first = {vm["name"]: vm["state"] for vm in before["list"]}
last = {vm["name"]: vm["state"] for vm in after["list"]}
assert first == last, f"Inventory or VM states changed: {first} -> {last}"
print("Original VM names and states preserved")
PY
}

# Abort before any lifecycle operation if inventory is unavailable or a name exists.
multipass list --format json >"${WORK_DIR}/before.json" || exit 2
"$PYTHON" - "${WORK_DIR}/before.json" "$VM_PREFIX" "$CLOUDMESH_VM_CONFIG" <<'PY'
import json, sys, yaml
inventory = json.load(open(sys.argv[1]))
assert not any(inventory.get("errors", [])), inventory.get("errors")
assert not any(vm["name"].startswith(sys.argv[2]) for vm in inventory["list"]), "Test name already exists"
config = {
    "default_cloud": "multipass", "username": sys.argv[2], "counter": 0,
    "clouds": {"multipass": {"enabled": True, "image": "24.04",
                             "cpus": 1, "memory": "1G", "disk": "8G"}}
}
with open(sys.argv[3], "w") as stream:
    yaml.safe_dump(config, stream)
PY
[ "$?" -eq 0 ] || exit 2

printf 'Disposable VM prefix: %s\n' "$VM_PREFIX"
echo "Using temporary configuration; the normal clouds.yaml is not modified."

check "CLI help" cmx_vm --help
check "Initialize existing config without overwriting it" cmx_vm config init
check "Config set integer" cmx_vm config set counter 0
check "Config get zero" cmx_vm config get counter
check "Config list" cmx_vm config list
check "Provider set" cmx_vm provider set multipass
check "Provider get" cmx_vm provider get
check "Provider list" cmx_vm provider list
check "Provider info" cmx_vm provider info
check "Images through multipass find" cmx_vm image
check "Local resource profiles" cmx_vm flavor
check "Key listing (no user-managed registry)" cmx_vm key list
check "Security-group listing (no cloud resources)" cmx_vm security-group list

CREATED+=("$EXPLICIT_VM")
check "Start with --name" cmx_vm start --name "$EXPLICIT_VM" || exit 1
check "Explicit name does not increment counter" assert_counter 0
check "Running state after launch" assert_state "$EXPLICIT_VM" Running
check "VM info" cmx_vm info "$EXPLICIT_VM"
check "Guest hostname" assert_hostname "$EXPLICIT_VM"
check "Successful command with no output" cmx_vm run "$EXPLICIT_VM" true
check "Failed guest command returns nonzero" expect_guest_failure
for format in table json yaml csv; do
    check "List format $format" assert_format "$format"
done
check "Restart running VM" cmx_vm restart "$EXPLICIT_VM"
check "Running state after restart" assert_state "$EXPLICIT_VM" Running
check "Stop VM" cmx_vm stop "$EXPLICIT_VM"
check "Stopped state" assert_state "$EXPLICIT_VM" Stopped
check "Start existing VM" cmx_vm start "$EXPLICIT_VM"
check "Running state after start" assert_state "$EXPLICIT_VM" Running
check "Suspend VM" cmx_vm suspend "$EXPLICIT_VM"
check "Suspended state" assert_state "$EXPLICIT_VM" Suspended
check "Resume suspended VM" cmx_vm start "$EXPLICIT_VM"
check "Running state after resume" assert_state "$EXPLICIT_VM" Running
check "Explicit start and resume keep counter unchanged" assert_counter 0
check "Shelve reports unsupported" expect_unsupported shelve "$EXPLICIT_VM"
check "Unshelve reports unsupported" expect_unsupported unshelve "$EXPLICIT_VM"
check "Delete dedicated VM" cmx_vm delete "$EXPLICIT_VM"
check "Dedicated VM absent after delete" assert_absent "$EXPLICIT_VM"

for index in 1 2; do
    name="${VM_PREFIX}-${index}"
    CREATED+=("$name")
    check "Automatic naming sequence $index" cmx_vm start || exit 1
    check "Persisted counter $index" assert_counter "$index"
    check "Generated VM $name is running" assert_state "$name" Running
    check "Delete generated VM $name" cmx_vm delete "$name"
    check "Generated VM absent" assert_absent "$name"
done

check "Other VM inventory and states preserved" assert_other_vms_unchanged
echo
echo "MANUAL: cmx vm ssh NAME and cmx vm login NAME, then type exit."
echo "SKIP: daemon reset, interactive CLI, account/Horizon/regions, SSH config, key mutation, security-group mutation."
echo "These skips and unsupported shelve/unshelve are not evidence of feature completeness."
[ "$FAILED" -eq 0 ]
