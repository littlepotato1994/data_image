FROM node:22-bookworm-slim

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @openai/codex
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY app ./app
COPY stl_toolkit ./stl_toolkit
COPY examples ./examples
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .

# Mount or configure trusted Codex/ChatGPT authentication at runtime.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

