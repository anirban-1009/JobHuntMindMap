FROM python:3.12-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies
# - texlive-xetex for LaTeX compilation
# - curl to download files
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-plain-generic \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency definitions
COPY pyproject.toml uv.lock README.md ./

# Install dependencies
# --frozen: ensure lock file is respected
# --no-dev: keep image small (unless running tests inside)
# --compile-bytecode: optimize startup time
RUN uv sync --frozen --no-dev

# Install Playwright browsers (Chromium only to save space)
# We need to activate the venv created by uv
ENV PATH="/app/.venv/bin:$PATH"
RUN playwright install chromium --with-deps

# Copy source code and config
COPY src/ ./src/
COPY config.sample.yaml ./config.sample.yaml

# Create directories for data and config
RUN mkdir -p /app/data /app/config /app/output /vault

# Default command
CMD ["python", "-m", "src.main"]
