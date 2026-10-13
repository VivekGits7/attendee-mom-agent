FROM python:3.11-bookworm

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --upgrade pip && pip install uv

COPY pyproject.toml uv.lock /app/

RUN uv sync --frozen --no-install-project --no-dev

COPY . /app/

ENTRYPOINT ["/app/.venv/bin/uvicorn"]

CMD ["app.main:app", "--host", "0.0.0.0", "--port", "8010"]
