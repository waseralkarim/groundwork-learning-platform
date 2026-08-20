# Groundwork API.
#
# Multi-stage on purpose: `dev` carries test tooling and runs with reload,
# `runtime` carries only what the process needs and runs as a non-root user.
# The C14 Containers track quotes this file, so it has to be exemplary.

# ---------------------------------------------------------------------- base --
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./

# ----------------------------------------------------------------------- dev --
FROM base AS dev

RUN uv pip install --system --no-cache '.[dev]' \
    && rm -rf /root/.cache

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY tests ./tests

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000", "--reload", "--reload-dir=/srv/app"]

# ------------------------------------------------------------------- runtime --
FROM base AS runtime

RUN uv pip install --system --no-cache '.' \
    && rm -rf /root/.cache \
    && pip uninstall -y uv

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Non-root. UID is fixed so bind-mounted volumes behave predictably.
RUN groupadd --gid 10001 groundwork \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin groundwork \
    && chown -R groundwork:groundwork /srv
USER 10001:10001

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000"]
