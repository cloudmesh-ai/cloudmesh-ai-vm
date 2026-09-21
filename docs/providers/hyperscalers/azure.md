# Azure VMs Provider

Integration for Microsoft Azure Virtual Machines using the \`libcloud\` abstraction layer.

## Configuration

\`\`\`yaml
azure:
  tenant_id: YOUR_TENANT_ID
  subscription_id: YOUR_SUB_ID
  client_id: YOUR_CLIENT_ID
  client_secret: YOUR_CLIENT_SECRET
  image: ubuntu-22.04
  size: Standard_DS1_v2
\`\`\`

## Usage Notes

- Authentication is handled via a Service Principal.
- Ensure you have created a Service Principal in your Azure AD.

## Examples

\`\`\`bash
cmx vm set azure
cmx vm start --name azure-node
\`\`\`
