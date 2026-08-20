# Groundwork lab broker.
#
# This is the one service that talks to a container runtime, so it is also the
# one that most needs to be small and boring. No shell utilities it does not
# use, no package manager in the final stage, non-root.

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./

FROM base AS dev
RUN uv pip install --system --no-cache '.[dev]' && rm -rf /root/.cache
COPY app ./app
COPY tests ./tests
EXPOSE 8100
CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8100", "--reload", "--reload-dir=/srv/app"]

FROM base AS runtime
RUN uv pip install --system --no-cache '.' \
    && rm -rf /root/.cache \
    && pip uninstall -y uv
COPY app ./app

# The broker runs as a non-root user. Reaching the Docker socket then depends on
# group membership, which compose.yaml grants explicitly — so the access is
# visible in configuration rather than implied by running as root.
RUN groupadd --gid 10002 broker \
    && useradd --uid 10002 --gid 10002 --no-create-home --shell /usr/sbin/nologin broker \
    && chown -R broker:broker /srv
USER 10002:10002

EXPOSE 8100
CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8100"]
