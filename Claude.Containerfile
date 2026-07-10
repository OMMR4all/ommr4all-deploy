FROM node:22-slim

# Install OS tools (libgl1 + libglib2.0-0 are needed by opencv)
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv git curl vim nano \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

# Install Claude Code via the new native installer
RUN curl -fsSL https://claude.ai/install.sh | bash

# Tell uv to ALWAYS use this specific folder for the virtual environment
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"
ENV EDITOR="vim"

# Put Claude's install directory AND the venv in the system PATH
ENV PATH="/root/.local/bin:/opt/venv/bin:$PATH"

CMD ["claude"]