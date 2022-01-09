import environ


@environ.config(prefix="TBOT_PSQL", frozen=True)
class DatabaseConfig:
    database = environ.var(help="PostgreSQL database name")
    user = environ.var(help="PostgreSQL database username")
    password = environ.var(help="PostgreSQL database password")
    host = environ.var(help="PostgreSQL database IP")
    port = environ.var(help="PostgreSQL database port")
    log_queries = environ.bool_var(default=False, help="Show SQLAlchemy query log")


@environ.config(prefix="TBOT_ACT", frozen=True)
class ActConfig:
    hash_secret = environ.var(default=None)

    @environ.config
    class Url:
        keywords = environ.var(default=None)
        templates = environ.var(name="TBOT_TG_URL_TEMPLATES", default=None)

    url = environ.group(Url)
