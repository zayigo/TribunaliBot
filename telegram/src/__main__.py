import logging
import random

import pause
import requests
import sentry_sdk
import telebot
from aiohttp import web
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from telebot.types import BotCommand

from logger.logger import log
from telegram.config import TelegramConfig
from telegram.src.handlers import bot

config = TelegramConfig.from_environ()

sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)

sentry_sdk.init(config.sentry, traces_sample_rate=1.0, integrations=[sentry_logging, SqlalchemyIntegration()])

routes = web.RouteTableDef()


def listener(messages):
    for m in messages:
        if m.content_type == 'text':
            log.debug(f"{m.chat.first_name} [{m.chat.id}]: {m.text}", extra={"tag": "TG-MSG"})


@web.middleware
async def error_middleware(request, handler):
    try:
        response = await handler(request)
        if response.status != 404:
            return response
        message = response.message
    except web.HTTPException as ex:
        log.exception("Webhook HTTP Exception", extra={"tag": "TG"})
        if ex.status != 404:
            raise
        message = ex.reason
    return web.json_response({'error': message})


@routes.post('/')
async def handle(request):
    request_body_dict = await request.json()
    update = telebot.types.Update.de_json(request_body_dict)
    try:
        bot.process_new_updates([update])
    except Exception:
        log.exception("Bot error", extra={"tag": "TG"})
    return web.Response()


@routes.get('/ok')
async def health_check(request):
    return web.Response(text="OK")


def main():
    templates = requests.get(config.url.templates).json()
    bot.remove_webhook()
    bot.set_webhook(url=config.main.webhook + config.main.token, drop_pending_updates=True)
    bot.set_update_listener(listener)
    bot.set_my_commands([BotCommand(name, desc) for name, desc in templates["italian"]["commands"].items()])
    app = web.Application(middlewares=[error_middleware], logger=log)
    app.add_routes(routes)
    log.info("Bot started", extra={"tag": "TG"})
    web.run_app(
        app,
        host="0.0.0.0",
        port=9181,
    )


if __name__ == "__main__":
    pause.milliseconds(random.randrange(1000, 5000))
    main()
