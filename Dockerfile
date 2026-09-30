FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY test_images ./test_images
COPY eval ./eval
COPY data ./data
ENV PORT=8000
# Secrets (ANTHROPIC_API_KEY, ANTHROPIC_WORKSPACE_ID) come from the host's environment, never the image
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
