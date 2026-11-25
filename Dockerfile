FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 JEWELMENTOR_DB=/app/runtime/jewelmentor.db
WORKDIR /app
RUN useradd --uid 10001 --create-home appuser && mkdir -p /app/runtime && chown appuser:appuser /app/runtime
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir .
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["jewelmentor", "serve", "--host", "0.0.0.0", "--port", "8000"]
