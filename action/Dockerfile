FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY cifi/ ./cifi/

RUN pip install --no-cache-dir .

COPY action/entrypoint.py /entrypoint.py

ENTRYPOINT ["python", "/entrypoint.py"]
