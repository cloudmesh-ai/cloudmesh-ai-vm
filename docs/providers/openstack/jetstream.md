# Jetstream Provider

Jetstream provides high-performance computing (HPC) and cloud environments based on OpenStack.

## Configuration

```yaml
jetstream:
  flavour: m1.small
  image: ubuntu-22.04
  auth: /path/to/jetstream/auth.yaml
  security_group: default
```

## Usage Notes

- **Authentication**: Jetstream requires a credentials file in YAML format. This file should contain your username, password, and auth URL.

## Examples

```bash
cmx vm set jetstream
cmx vm start --name jetstream-node-1
```
