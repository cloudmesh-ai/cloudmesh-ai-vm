# Contributing

We welcome contributions to make \`cloudmesh-ai-vm\` more powerful and supportive of more clouds!

## How to Contribute

### Adding a New Provider

1. **Check libcloud**: See if the provider is already supported by \`libcloud\`. If so, inherit from \`LibcloudManager\`.
2. **Implement Interface**: If it's a custom provider, inherit from \`CloudBaseManager\` and implement all abstract methods.
3. **Add Config**: Update the \`clouds.yaml\` example in the documentation to show required credentials.
4. **Register**: Add your provider to the \`PROVIDERS\` map in \`src/main.py\`.
5. **Test**: Create a new test file in \`tests/\` using \`unittest.mock\`.

### Development Workflow

- **Branching**: Create a feature branch from \`main\`.
- **Commits**: Use descriptive commit messages.
- **PRs**: Submit a Pull Request with a clear description of the changes and examples of how to use the new feature.

## Coding Standards

- Follow **PEP 8** guidelines.
- Use **type hinting** for all method signatures.
- Ensure all new functionality is covered by **unit tests**.
