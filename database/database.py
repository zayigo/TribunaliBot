from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from database.config import DatabaseConfig

config = DatabaseConfig.from_environ()

url = URL.create(
    "postgresql",
    username=config.user,
    password=config.password,
    host=config.host,
    port=config.port,
    database=config.database
)

engine = create_engine(url, echo=config.log_queries, future=True)

SessionFactory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
