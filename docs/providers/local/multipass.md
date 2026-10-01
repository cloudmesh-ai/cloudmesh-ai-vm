# Multipass Provider

Multipass manages local Ubuntu VMs through Canonical's CLI. This provider uses
subprocess argument lists and machine-readable Multipass JSON for inventory.

## Configuration

The default file is ~/.config/cloudmesh/clouds.yaml. Set CLOUDMESH_VM_CONFIG
to use a separate file, for example during disposable verification.

~~~yaml
default_cloud: multipass
username: sugwu
counter: 0
clouds:
  multipass:
    enabled: true
    image: "24.04"
    cpus: 2
    memory: 2G
    disk: 10G
~~~

~~~bash
cmx vm config init
cmx vm provider set multipass
cmx vm config get counter
~~~

Configuration initialization preserves existing values. Configuration set
parses YAML scalars, so counter and CPU values remain integers.

## Naming and lifecycle

~~~bash
# Reserves the next counter and launches sugwu-1.
cmx vm start

# Exact name, with no counter increment.
cmx vm start --name multipass-demo

cmx vm info multipass-demo
cmx vm run multipass-demo hostname
cmx vm run multipass-demo "printf '%s\n' 'hello world' | cat"
cmx vm restart multipass-demo
cmx vm stop multipass-demo
cmx vm start multipass-demo
cmx vm suspend multipass-demo
cmx vm start multipass-demo

# Permanently removes only this disposable VM.
cmx vm delete multipass-demo
~~~

Start launches an absent name, resumes a Stopped or Suspended VM with
multipass start, and leaves a Running VM running. Deleted and transitional
states produce an error rather than an attempted replacement launch.
Restart uses multipass restart and expects a running VM.

Automatic names use the configured username with underscores replaced by
hyphens and a persistent global counter. Existing names are skipped.
The counter reserves a number before launch, so a failed launch can consume
a number. --name, positional names, hostlists, and --range leave it unchanged.
Choose one target selector per invocation.

~~~bash
cmx vm start --count 2
cmx vm start "node[1-3]"
cmx vm start --range 1-3
~~~

Count on start creates new names. Count on other lifecycle commands selects
from inventory; Multipass does not expose creation timestamps in its list
response, so its order is not proof of which machines were created last.
Use explicit names when managing existing VMs.

## Inventory and guest access

~~~bash
cmx vm list vms
cmx vm list --json
cmx vm list vms --format yaml
cmx vm list vms --csv
cmx vm list --all --table
cmx vm image
cmx vm flavor
cmx vm provider info

# Interactive managed shells. Type exit to close each session.
cmx vm ssh multipass-demo
cmx vm login multipass-demo
~~~

JSON and YAML contain VM records; CSV contains a header and one row per VM.
Machine-readable output has no table heading or status prose. Native state,
addresses, and image information are retained alongside shared name, status,
and IP fields.

Run executes sh -lc inside the guest through multipass exec. Quoting and pipes
are interpreted there, without a host shell. Nonzero guest exits propagate
as CLI failures. Successful commands with no output also succeed.

SSH and login use multipass shell, which handles its own connection credentials.
The provider does not invent a user key path or cloud security groups.
Key and security-group inventories are empty because Multipass has no such
user-managed registries.

## Capabilities and remaining work

| Command or feature | Multipass behavior |
| --- | --- |
| start, stop, restart, suspend, delete | Implemented; live host verification required. |
| info, run | Implemented; live host verification required. |
| list, image, flavor, provider/config commands | Implemented; live host verification required. |
| ssh, login | Interactive managed shell; manual verification required. |
| shelve, unshelve | Unsupported with a nonzero CLI exit. |
| key upload/delete, security-group mutations, regions | No equivalent cloud API; unsupported. |
| account, Horizon | No cloud account allocation or Horizon dashboard. |
| ssh-config | No generated key-based SSH configuration; still a CLI gap. |
| reset | macOS provider daemon operation; excluded from disposable tests. |
| interactive CLI mode | Separate manual validation remains. |
| Other local and remote providers | Outside this Multipass contribution's live test scope. |

Multipass suspension preserves the VM and its resources. It does not implement
OpenStack shelving or release an allocation. Stop is not labeled as shelve.
Resume a stopped or suspended instance with start.

The reset command restarts the macOS Multipass daemon rather than just a named
VM. It is not included in the verification sequence that preserves other VMs.

## Verification

~~~bash
python -m pip install pytest
python -m pytest -q tests/unit --ignore=tests/unit/test_vm.py
set -o pipefail
bash tests/bin/verify_multipass_week5.sh 2>&1 | tee verification-week5.txt
~~~

The excluded legacy test imports the separate cloudmesh.ai.cmc package, which
is not a dependency of this standalone VM package. This exclusion is not proof
that the CMC integration works.

The shell script launches and deletes three uniquely named disposable VMs
sequentially with a temporary configuration. It validates native states,
guest output, list formats, counter persistence, and preservation of the
original inventory. Its expected-unsupported checks validate error behavior,
not successful shelving. Manual and skipped features are printed separately.
Interrupted or failed runs attempt cleanup of only the dedicated test names.

The earlier Mac evidence recorded 8 passes and 3 failures. The new code and
script are regression-tested with mocks and a simulated Multipass executable.
A new real Mac log is still required; simulated results do not replace it.

## Troubleshooting

If an editable install intermittently reports No module named cloudmesh.ai.command,
reinstall the checkout using python -m pip install --no-deps . and verify the
active Python and cmx are in the same virtual environment. The prior editable
namespace failure has not been fully diagnosed.

If start reports a Deleted or transitional state, inspect multipass info NAME.
Recover or remove that exact dedicated instance deliberately before reusing
its name. The provider does not run a global purge.

Canonical references:
- [Start](https://documentation.ubuntu.com/multipass/latest/reference/command-line-interface/start/)
- [Info](https://documentation.ubuntu.com/multipass/latest/reference/command-line-interface/info/)
- [Exec](https://documentation.ubuntu.com/multipass/latest/reference/command-line-interface/exec/)
- [Find](https://documentation.ubuntu.com/multipass/latest/reference/command-line-interface/find/)
