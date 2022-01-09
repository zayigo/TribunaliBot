import json
import sys

from logger.logger import log
from tbot import start_from_cronicle

data = json.load(sys.stdin)

log.info(f"Starting Cronicle job - {data}")

params = data["params"]

start_from_cronicle(
    notifications=bool(params["notifications"]),
)
