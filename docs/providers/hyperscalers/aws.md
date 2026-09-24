# AWS EC2 Provider

Integration for Amazon Elastic Compute Cloud (EC2) using the `libcloud` abstraction layer.

## Configuration

```yaml
aws:
  access_key: YOUR_ACCESS_KEY
  secret_key: YOUR_SECRET_KEY
  region: us-east-1
  image: ami-0c55b159cbfafe1f0
  size: t2.micro
```

## Usage Notes

- Ensure your AWS IAM user has the necessary permissions to create and manage EC2 instances.
- Images (AMIs) are region-specific.

## Examples

```bash
cmx vm set aws
cmx vm start --name aws-test-vm
```
