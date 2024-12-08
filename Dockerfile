FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    apt-get clean
RUN rm -rf /var/lib/apt/lists/*

WORKDIR /bourso2ynab

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
COPY uv.lock pyproject.toml .
RUN /root/.local/bin/uv sync --frozen

COPY . .

# CMD /root/.local/bin/uv run python3 -m flask run --host=0.0.0.0
CMD /root/.local/bin/uv run gunicorn -b 0.0.0.0:5000 "app:create_app()"
