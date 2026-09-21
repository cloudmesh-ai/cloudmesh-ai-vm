# Installation Guide

This guide will walk you through the process of installing \`cloudmesh-ai-vm\` on your local machine.

## Prerequisites

- **Python 3.x**: Ensure you have Python 3.8 or higher installed.
- **Pip**: The Python package installer.

## Setup Steps

### 1. Clone the Repository

\`\`\`bash
git clone https://github.com/your-repo/cloudmesh-ai-vm.git
cd cloudmesh-ai-vm
\`\`\`

### 2. Install Dependencies

We recommend using a virtual environment to avoid dependency conflicts.

\`\`\`bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
pip install -r requirements.txt
\`\`\`

### 3. Install the CLI Tool

Install the package in editable mode so you can make changes to the source code:

\`\`\`bash
pip install -e .
\`\`\`

## Verifying Installation

Run the following command to ensure the CLI is installed and working:

\`\`\`bash
cmx --help
\`\`\`

If you see the help menu, you are ready to go!
