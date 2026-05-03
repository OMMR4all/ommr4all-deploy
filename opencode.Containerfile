FROM node:22-slim

# Install OS tools (tmux is strictly required by Oh My OpenAgent for background jobs)
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv git curl tmux jq unzip \
    && rm -rf /var/lib/apt/lists/*

# Install uv (keeps your python workflow intact)
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

# Install Bun (Oh My OpenAgent runs on Bun)
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:$PATH"

# Install OpenCode natively
RUN npm install -g opencode-ai

# Setup your virtual environment path
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"
ENV PATH="/opt/venv/bin:$PATH"

CMD ["opencode"]