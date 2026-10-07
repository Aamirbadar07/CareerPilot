FROM python:3.11-slim

# Pango is WeasyPrint's text engine; Carlito is the metric-compatible Calibri the template names.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-crosextra-carlito \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev
COPY . .
ENV PATH="/app/.venv/bin:$PATH"

# No --proxy-headers: it would rewrite the client address from the *first* X-Forwarded-For
# entry, which the caller writes. The rate limit reads the header itself, from the right
# (app/core/rate_limit.py, TRUSTED_PROXY_HOPS).
# `timeout ... || echo`: migrations must not be able to stop the app from starting. Against
# an unreachable database alembic blocks with no output, so the container never listens and
# every request becomes a blank 500 with nothing in the logs to explain it. Starting anyway
# gives /health a chance to say what is wrong.
CMD ["sh", "-c", "timeout 60 alembic upgrade head || echo 'migrations failed or timed out; starting anyway, see /health'; uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
