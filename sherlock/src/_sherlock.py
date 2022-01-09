from datetime import datetime as dt
import re

import pause
import requests
from fuzzywuzzy import fuzz, process  # type: ignore
from sqlalchemy import and_
from sqlalchemy.future import select
from sqlalchemy.sql.expression import null

from database.database import SessionFactory
from database.models import Message, Act, Tracking
from logger.logger import log

RE_HTML = r"<.*?>"
RE_WHITESPACE = r"\s+|„|“|”|\.{2,}| {2,}"


class Sherlock:
    def __init__(
        self, keywords: str, config_poll_time: int, batch_size: int, tg_channel_id: int
    ):
        self.keywords = requests.get(keywords, timeout=60).json() if keywords else []
        self.config_poll_time = config_poll_time
        self.poll_time = config_poll_time
        self.batch_size = batch_size
        self.act = None
        self.batch = []
        self.tg_channel_id = tg_channel_id
        self.role = "SHE"

    def update_poll_time(self, increase=False):
        time_before = self.poll_time
        if increase and self.poll_time < self.config_poll_time:
            self.poll_time += 1
            log.info(
                f"Increased poll time {time_before} -> {self.poll_time}",
                extra={"tag": self.role},
            )
        elif not increase and self.poll_time > 0:
            self.poll_time -= 1
            log.info(
                f"Decreased poll time {time_before} -> {self.poll_time}",
                extra={"tag": self.role},
            )

    def poll(self):
        while True:
            with SessionFactory() as session:
                # UPDATE permits SET processed_at = TO_TIMESTAMP('2021-01-01', 'YYYY-MM-DD')
                stmt = (
                    select(Act)
                    .where(and_(Act.processed_at == null(), Act.error.is_(None)))
                    .order_by(Act.timestamp.asc())
                    .limit(self.batch_size)
                )
                self.batch = session.execute(stmt).scalars().all()
                log.info(f"Processing {len(self.batch)} acts", extra={"tag": self.role})
                if not self.batch:
                    self.update_poll_time(increase=True)
                for act in self.batch:
                    self.update_poll_time()
                    self.act = act
                    log.info(self.act)
                    start_time = dt.now()
                    try:
                        self.clean()
                        self.evaluate()
                    except Exception as e:
                        self.act.error = repr(e)
                        log.exception(
                            f"Error while processing act {self.act}",
                            extra={"tag": self.role},
                        )
                        session.commit()
                        continue
                    if self.act.notify:
                        log.info("Creating messages", extra={"tag": self.role})
                        self.create_messages(session)
                    end_time = dt.now()
                    self.act.process_time = end_time - start_time
                    self.act.processed_at = end_time
                    session.commit()
            log.info(
                f"Finished processing acts, going to sleep for {self.poll_time} seconds",
                extra={"tag": self.role},
            )
            pause.seconds(self.poll_time)

    def clean(self):
        try:
            self.act.text = re.sub(RE_HTML, " ", self.act.text)
            self.act.text = re.sub(RE_WHITESPACE, " ", self.act.text).strip()
            self.act.text = self.act.text[0].upper() + self.act.text[1:]
        except IndexError:
            self.act.text = ""
        if self.act.info.extra_info:
            for k, v in self.act.info.extra_info.items():
                v = re.sub(RE_HTML, " ", v)
                v = re.sub(RE_WHITESPACE, " ", v).strip()
                self.act.info.extra_info[k] = v
        for doc in self.act.info.docs:
            if doc.title:
                title = re.sub(RE_HTML, " ", doc.title)
                doc.title = re.sub(RE_WHITESPACE, " ", title).strip()

    def create_messages(self, session):
        text = self.act.get_telegram_text()
        if self.act.is_tlc:
            user_ids = Tracking.get_users_id(
                session, court_id=self.act.court_id, only_tlc=True
            )
            self.act.messages.append(
                Message(username=self.tg_channel_id, text=text, url_preview=True)
            )
        else:
            user_ids = Tracking.get_users_id(session, court_id=self.act.court_id)
        for u_id in user_ids:
            self.act.messages.append(
                Message(user_id=u_id, text=text, url_preview=False)
            )

    def evaluate(self):
        text = self.act.full_text.lower()
        self.act.info.matches = dict(
            process.extractBests(
                text,
                self.keywords["whitelist"],
                scorer=fuzz.token_set_ratio,
                score_cutoff=81,
            )
        )
        self.act.info.blacklist = dict(
            process.extractBests(
                text,
                self.keywords["blacklist"],
                scorer=fuzz.token_set_ratio,
                score_cutoff=95,
            )
        )
        self.act.info.isp = dict(
            process.extractBests(
                text, self.keywords["isp"], scorer=fuzz.token_set_ratio, score_cutoff=90
            )
        )
        if text:
            for kw in self.keywords["exact"]:
                if kw in text:
                    self.act.is_tlc = True
                    return
        if self.act.info.blacklist:
            if self.act.info.matches:
                log.info(
                    f"Found blacklisted word with match {self}",
                    extra={"tag": self.role},
                )
            elif self.act.info.isp:
                log.info(
                    f"Found blacklisted word with isp {self}", extra={"tag": self.role}
                )
            self.act.is_tlc = False
            return
        if self.act.info.matches or self.act.info.isp:
            self.act.is_tlc = True
