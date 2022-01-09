import environ


@environ.config(prefix="TBOT_SCAN", frozen=False)
class ScanConfig:
    sentry = environ.var()
    notifications = environ.bool_var(default=False)
    support_channel = environ.var(name="TBOT_TG_SUPPORT_CHAT_ID")
