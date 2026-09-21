!!! note "Assignment W5.1: VMs via python (libcloud)"
    This document serves as a guide and roadmap for improving the `cloudmesh-ai-vm` tool as part of Assignment W5.1. The goal is to transform this draft tool into a robust hybrid multicloud management utility.

      **1. Objectives**

      The primary goal is to engage in DevOps development activities, improve the codebase, and ensure consistent functionality across multiple cloud providers.

      **1.1 Core Requirements**

      1. **Cloud Implementation**: Implement or improve commands for one or more cloud providers (Local, OpenStack, or Hyperscalers).
      2. **Code Understanding**: Master the interaction between the Click-based CLI, the `clouds.yaml` configuration, and the provider interfaces.
      3. **Feature Completeness**: Implement all mentioned commands and ensure they work across selected clouds.
      4. **Validation**: Create a shell script that demonstrates the success or failure of each command.
      5. **Collaboration**: Use GitHub (forking, cloning, and Pull Requests) to collaborate with peers.
      6. **Documentation**: Update the markdown documentation with cloud-specific examples.

      **2. Improvement Roadmap**

      Based on the current state of the project, here are the recommended areas for improvement:

      **2.1 Feature Gaps (High Priority)**

      Some commands mentioned in the assignment are currently missing or incomplete:
      - **Implement missing commands**: Identify which commands are missing and implement them. Before implementation discuss on Piazza.
      - **Enhance commands**: Evaluate a command such as `cmx vm list`: Implement missing features and options. An example is to implement output formatting options (`--json`, `--yaml`, `--csv`, `--table`) to allow for better integration with other tools.
      - **Refine Naming Logic**: Ensure that `cmx vm start` correctly handles the `{username}-{counter}` logic and that the `--name` override works without incrementing the counter.

        **2.2 Provider-Specific Improvements**

        Depending on the chosen clouds, focus on:

        - **OpenStack**: The OpenStack provider for Jetstream and Chameleon Cloud have not been tested and are only drafted. Make sure to provide a complete implementation of all the commands.
        - **Hyperscalers**: (Optional) Improve the `libcloud` abstraction to ensure consistency between AWS, Azure, and Google.
        - **Local Providers**: Ensure Multipass, WSL2, and VirtualBox share a consistent lifecycle (start, stop, delete). Figure out what to do with shelve/unshelve.

        **2.3 Quality Assurance & Testing**

        - **Shell Script Validation**: Create a `verify_vm.sh` script that iterates through all commands:
          ```bash
          # Example verification loop
          COMMANDS=("start" "info" "stop" "delete")
          for cmd in "${COMMANDS[@]}"; do
            echo "Testing cmx vm $cmd..."
            cmx vm $cmd || echo "FAILED"
          done
          ```

        - **Unit Testing**: (Optional) Increase coverage in `tests/unit` and `tests/smoke` for new provider implementations.

        **2.4 Documentation & User Experience**

        - **Expand Provider Guides**: Add real-world usage examples and common troubleshooting tips to the `docs/providers/` pages.
        - **Manual Page**: Ensure `docs/manual.md` is always up-to-date with the latest CLI changes.

        **3. Collaboration Guide (GitHub Flow)**

        To work effectively with a larger group, follow these DevOps practices:

        - **Communicate**: Although you use git, communication is important. Work needs to be split up and tasks need to be assigned. Create GitHub issues to coordinate the tasks.
        - **Fork and Clone**: Fork the repository to your own account and clone it locally.
        - **Feature Branches**: Never work directly on `main`. Create a branch for each feature:
           `git checkout -b feature/add-login-command`
        - **Atomic Commits**: Make small, frequent commits with descriptive messages.
        - **Pull Requests (PRs)**: Submit PRs to the original repository. Provide a clear description of the changes and evidence (logs/screenshots) that the commands work.
        - **Peer Review**: Review your colleagues' PRs to learn from their implementation and ensure code quality.

