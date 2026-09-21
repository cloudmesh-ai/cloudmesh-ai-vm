# Chameleon Cloud Provider

Chameleon Cloud is a testbed for cloud research, offering both bare-metal and virtualized resources via OpenStack.

## Configuration

```yaml
chameleon:
  flavour: c1.small
  image: rocky-linux-8
  auth: /path/to/chameleon/auth.yaml
  project_name: CH-XXXXXX
  site: CHI@TACC
```

## Advanced Feature: Hardware Reservations

Unlike standard clouds, Chameleon allows you to reserve specific hardware (e.g., specific CPU architectures) for a set period.

### Creating a Reservation

You can use the `reservation` command to create a lease.

**Example: 2-day lease for a Skylake node**

```bash
cmx vm reservation --name my-research-lease --node-type compute_skylake --count 1 --duration 2
```

**Example: Explicit dates**

```bash
cmx vm reservation --name my-lease --node-type compute_skylake --count 1 --start "2026-10-01 08:00" --end "2026-10-03 08:00"
```

## Examples

```bash
cmx vm set chameleon
cmx vm start
```
