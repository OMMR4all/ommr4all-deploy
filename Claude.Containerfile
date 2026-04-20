FROM node:22-slim

# Install OS tools
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv git curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv and Claude
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh
RUN npm install -g @anthropic-ai/claude-code

# Tell uv to ALWAYS use this specific folder for the virtual environment
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"
# Put the venv in the system PATH so Claude finds Python instantly
ENV PATH="/opt/venv/bin:$PATH"

CMD ["claude"]