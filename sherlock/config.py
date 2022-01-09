import environ


@environ.config(prefix="TBOT_SHERLOCK", frozen=True)
class SherlockConfig:
    sentry = environ.var()

    keywords = environ.var(help="Amazon S3 URL", default=None)

    poll_time = environ.var(help="Time in seconds between updates", converter=int)
    batch_size = environ.var(help="Number of permits to process before going back to sleep", converter=int)

    tg_channel_id = environ.var(name="TBOT_TG_CHANNEL_CHAT_ID")
