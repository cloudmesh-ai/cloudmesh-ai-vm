# Google GCE Provider

Integration for Google Compute Engine (GCE) using the \`libcloud\` abstraction layer.

## Configuration

\`\`\`yaml
google:
  project_id: YOUR_PROJECT_ID
  private_key: /path/to/service-account.json
  image: ubuntu-2204-lts
  size: n1-standard-1
\`\`\`

## Usage Notes

- Requires a Google Cloud Service Account JSON key file.
- Ensure the Compute Engine API is enabled for your project.

## Examples

\`\`\`bash
cmx vm set google
cmx vm start --name gcp-vm
\`\`\`
