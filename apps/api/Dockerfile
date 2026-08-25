FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY apps/api/requirements.txt /srv/requirements.txt
RUN pip install -r /srv/requirements.txt

COPY packages/python-sdk /srv/packages/python-sdk
RUN pip install -e /srv/packages/python-sdk

COPY apps/api /srv/apps/api
COPY migrations /srv/migrations
COPY alembic.ini /srv/alembic.ini

WORKDIR /srv/apps/api
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
