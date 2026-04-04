FROM python:3.12-slim

WORKDIR /app

# Install dependencies first — this layer is cached until pyproject.toml changes.
# Uses a stub cifi package so pip can resolve deps without the real source.
COPY pyproject.toml .
RUN mkdir -p cifi && touch cifi/__init__.py && \
    pip install --no-cache-dir . && \
    rm -rf cifi

# Install the real package without re-downloading deps
COPY cifi/ ./cifi/
RUN pip install --no-cache-dir --no-deps .

COPY action/entrypoint.py /entrypoint.py

ENTRYPOINT ["python", "/entrypoint.py"]
