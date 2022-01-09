FROM python:3.9-slim as base

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1

RUN pip install pipenv

RUN apt-get update && apt-get install --no-install-recommends -y gcc libc-dev git

# Install python dependencies in /.venv
COPY Pipfile .
# COPY Pipfile.lock .
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

FROM base AS python-deps

ARG TBOT_PSQL_DATABASE
ENV TBOT_PSQL_DATABASE $TBOT_PSQL_DATABASE

ARG TBOT_PSQL_USER
ENV TBOT_PSQL_USER $TBOT_PSQL_USER

ARG TBOT_PSQL_PASSWORD
ENV TBOT_PSQL_PASSWORD $TBOT_PSQL_PASSWORD

ARG TBOT_PSQL_HOST
ENV TBOT_PSQL_HOST $TBOT_PSQL_HOST

ARG TBOT_PSQL_PORT
ENV TBOT_PSQL_PORT $TBOT_PSQL_PORT

COPY --from=base /.venv /.venv
ENV PATH="/.venv/bin:$PATH"

RUN useradd --create-home tbot
WORKDIR /home/tbot
USER tbot

COPY ./logger ./logger
COPY ./database ./database