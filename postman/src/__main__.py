import logging

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from logger.logger import log
from postman.config import PostmanConfig
from postman.src.postman import Postman

config = PostmanConfig.from_environ()

sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)

sentry_sdk.init(
    config.sentry,
    traces_sample_rate=1.0,
    integrations=[sentry_logging, SqlalchemyIntegration()],
)


def main():
    log.info("Starting postman worker", extra={"tag": "POST"})
    msg = Postman(
        token=config.token,
        attempts=config.attempts,
        config_poll_time=config.poll_time,
        batch_size=config.batch_size,
    )
    msg.poll()


if __name__ == "__main__":
    main()
