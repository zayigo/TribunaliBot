import environ


@environ.config(prefix="TBOT_MESSENGER", frozen=True)
class PostmanConfig:
    sentry = environ.var()
    poll_time = environ.var(help="Time in seconds between updates", converter=int)
    batch_size = environ.var(
        help="Number of messages to process before going back to sleep", converter=int
    )
    attempts = environ.var(help="Max retries", converter=int)
    token = environ.var(name="TBOT_TG_MAIN_TOKEN")

    @environ.config
    class Url:
        templates = environ.var(name="TBOT_TG_URL_TEMPLATES")
        deeplink = environ.var(name="TBOT_TG_MAIN_DEEPLINK")

    url = environ.group(Url)
