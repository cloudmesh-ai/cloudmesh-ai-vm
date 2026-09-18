# WSL2 Provider

The WSL2 provider allows you to manage Windows Subsystem for Linux distributions as if they were VMs.

## Configuration

\`\`\`yaml
wsl2:
  distro: Ubuntu-22.04
  ssh_link: true
\`\`\`

## Special Feature: SSH Linking

If \`ssh_link: true\` is set, \`cloudmesh-ai-vm\` will attempt to symbolically link your host's \`.ssh\` directory into the WSL2 distribution. This allows you to share your SSH keys and config between Windows and Linux seamlessly.

## Examples

\`\`\`bash
cmc vm set wsl2
cmc vm start
\`\`\`
