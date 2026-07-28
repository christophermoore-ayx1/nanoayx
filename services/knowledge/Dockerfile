FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd --gid 1000 nanoayx \
    && useradd --uid 1000 --gid nanoayx --create-home nanoayx \
    && mkdir -p /data /knowledge/drive \
    && chown -R nanoayx:nanoayx /app /data /knowledge

COPY --chown=nanoayx:nanoayx app ./app
COPY --chown=nanoayx:nanoayx tests ./tests

USER nanoayx

EXPOSE 8787

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787"]
