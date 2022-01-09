import locale
import logging
import sys

import click
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from database.database import SessionFactory
from database.models import Message
from logger.logger import log
from scrapers.config.config import ScanConfig

from scrapers.tar import Scraper

locale.setlocale(locale.LC_ALL, "it_IT.utf8")

config = ScanConfig.from_environ()

sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)

sentry_sdk.init(config.sentry, traces_sample_rate=1.0, integrations=[sentry_logging, SqlalchemyIntegration()])


class Commander:
    def __init__(self, notification):
        self.notification = notification
        self.start_permit_count = 0

    def send_and_log(self, text: str):
        log.info(text)
        with SessionFactory() as session:
            Message.create(session, text=f"<b>{text}</b>", username=config.support_channel, priority=1000)

    def notify(self, action):
        if action == "end":
            text = '✅  TAR scan completed'
        elif action == "error":
            text = '🆘  TAR scan error'
        elif action == "start":
            text = 'ℹ️  TAR scan started'
        self.send_and_log(text=text)

    def start(self):
        log.info(f"Notifications: {self.notification}")
        scraper = Scraper(notification=self.notification)
        self.notify(action="start")
        try:
            scraper.scan()
        except KeyboardInterrupt:
            log.info("Got KeyboardInterrupt, quitting...")
        except Exception:
            log.exception("Commander error")
            self.notify(action="error")
        else:
            self.notify(action="end")


@click.command()
@click.option('--on/--off', 'notifications', default=config.notifications, help="Enable notifications")
# @click.option('--court-id', "-t", "court_ids", required=False, type=str, multiple=True)
def main(notifications: bool):
    start_tbot(notifications)


def start_tbot(notifications: bool):
    # if court_ids:
    #     log.info(f"Scan limited to {court_ids}", extra={"tag": "SCAN"})
    config.notifications = notifications
    commander = Commander(notification=config.notifications)
    commander.start()
    sys.exit(0)


def start_from_cronicle(notifications: bool):
    start_tbot(notifications)


if __name__ == "__main__":
    main()
