import logging
import sys

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from logger.logger import log
from sherlock.config import SherlockConfig
from sherlock.src._sherlock import Sherlock

config = SherlockConfig.from_environ()

sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)

sentry_sdk.init(
    config.sentry,
    traces_sample_rate=1.0,
    integrations=[sentry_logging, SqlalchemyIntegration()],
)


def main():
    log.info("Starting Sherlock", extra={"tag": "SHE"})
    sherlock = Sherlock(
        keywords=config.keywords,
        config_poll_time=config.poll_time,
        batch_size=config.batch_size,
        tg_channel_id=config.tg_channel_id
    )
    sherlock.poll()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Got KeyboardInterrupt, quitting", extra={"tag": "SHE"})
        sys.exit(0)
