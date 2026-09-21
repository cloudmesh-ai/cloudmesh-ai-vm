# VirtualBox Provider

The VirtualBox provider manages headless VMs using the `VBoxManage` CLI tool.

## Configuration

```yaml
vbox:
  image: ubuntu-server-22.04.iso
  memory: 2048
  cpus: 1
```

## Usage Notes

- VMs are started in **headless mode** by default to maximize performance and reduce overhead.
- Ensure `VBoxManage` is in your system `PATH`.

## Examples

```bash
cmx vm set vbox
cmx vm start
```
