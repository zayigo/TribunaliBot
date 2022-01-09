import environ


@environ.config(prefix="TBOT_TG", frozen=True)
class TelegramConfig:
    sentry = environ.var()

    @environ.config
    class Main:
        token = environ.var(help="Telegram bot token")
        name = environ.var(help="Bot name")
        webhook = environ.var(help="Webhook url")
        deeplink = environ.var(help="Deeplink url")
        maintenance = environ.bool_var(default=False, help="Trigger maintenance mode")

    @environ.config
    class Support:
        chat_id = environ.var(help="Support group chat id")

    @environ.config
    class Channel:
        chat_id = environ.var()
        name = environ.var()

    @environ.config
    class Url:
        donate = environ.var()
        templates = environ.var()

    main = environ.group(Main)
    channel = environ.group(Channel)
    url = environ.group(Url)
