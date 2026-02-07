FROM python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies (for LaTeX and Playwright)
# - playwright needs deps (installed later)
# - texlive-xetex for LaTeX compilation (includes fonts)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-plain-generic \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies manually (before pip to cache)
# This is a bit complex as `playwright install-deps` usually needs playwright installed first.
# We will do it in a cleaner step after pip install.

# Copy dependency definition
COPY pyproject.toml README.md ./

# Install python dependencies including playwright
RUN pip install --no-cache-dir .

# Install Playwright browsers and system dependencies
RUN playwright install chromium --with-deps

# Copy source code
COPY src/ ./src/
COPY config.sample.yaml ./config.sample.yaml

# Create directories for data and config
RUN mkdir -p /app/data /app/config /app/output /vault

# Default command
CMD ["python", "-m", "src.main"]
