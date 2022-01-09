import logging
import logging.config

import coloredlogs  # type: ignore
import yaml

# import os

# dirname = os.path.dirname(__file__)
# filename = os.path.join(dirname, "/config/logs_config.yaml")
filename = "./logger/config.yaml"

try:
    with open(filename, "r") as f:
        config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
except Exception as e:
    print(f"Errore caricamente impostazioni logging - {e}")

# Create a custom logger
log = logging.getLogger(__name__)
coloredlogs.install(
    # level="ERROR", this overwrites everything
    logger=log,
    fmt="%(asctime)s %(programname)s %(levelname)s %(message)s",
    # fmt="%(asctime)s %(hostname)s %(programname)s %(levelname)s [%(tag)s] %(message)s",
)
