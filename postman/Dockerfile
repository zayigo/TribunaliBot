FROM tribunalibot-base:latest

ARG TBOT_MESSENGER_POLL_TIME
ENV TBOT_MESSENGER_POLL_TIME $TBOT_MESSENGER_POLL_TIME

ARG TBOT_MESSENGER_ATTEMPTS
ENV TBOT_MESSENGER_ATTEMPTS $TBOT_MESSENGER_ATTEMPTS

ARG TBOT_MESSENGER_SENTRY
ENV TBOT_MESSENGER_SENTRY $TBOT_MESSENGER_SENTRY

ARG TBOT_TG_MAIN_TOKEN
ENV TBOT_TG_MAIN_TOKEN $TBOT_TG_MAIN_TOKEN

ARG TBOT_TG_URL_TEMPLATES
ENV TBOT_TG_URL_TEMPLATES $TBOT_TG_URL_TEMPLATES

COPY . ./postman

ENTRYPOINT ["python"]

CMD ["-m", "postman.src"]