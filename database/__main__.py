from database import models
from database.database import engine
from logger.logger import log


def create_tables():
    log.info("Creating tables", extra={"tag": "DB"})
    models.Base.metadata.create_all(engine)


if __name__ == "__main__":
    create_tables()
