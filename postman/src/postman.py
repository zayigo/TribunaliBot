import datetime as dt
import re
import sys

import pause
import requests
import telebot
from sqlalchemy import and_
from sqlalchemy.future import select
from sqlalchemy.sql.expression import false

from database.database import SessionFactory
from database.models import Message
from logger.logger import log
from postman.config import PostmanConfig

config = PostmanConfig.from_environ()


class Postman():
    def __init__(self, token: str, attempts: int, config_poll_time: int, batch_size: int):
        self.token = token
        self.attempts = attempts
        self.config_poll_time = config_poll_time
        self.poll_time = config_poll_time
        self.batch_size = batch_size
        self.msg = None
        self.messages = None
        self.bot = telebot.TeleBot(self.token, threaded=False)
        self.templates = requests.get(config.url.templates, timeout=60).json()
        self.role = "POST"

    def update_poll_time(self, increase=False):
        time_before = self.poll_time
        if increase and self.poll_time < self.config_poll_time:
            self.poll_time += 1
            log.info(f"Increased poll time {time_before} -> {self.poll_time}", extra={"tag": self.role})
        elif not increase and self.poll_time > 0:
            if self.msg.priority > 0:
                self.poll_time = 0
            else:
                self.poll_time -= 1
            log.info(f"Decreased poll time {time_before} -> {self.poll_time}", extra={"tag": self.role})

    def poll(self):
        try:
            while True:
                with SessionFactory() as session:
                    stmt = select(Message).where(
                        and_(Message.sent == false(), Message.error.is_(None))
                    ).order_by(Message.priority.desc(), Message.timestamp.asc()).limit(self.batch_size)
                    self.messages = session.execute(stmt).scalars().all()
                    log.info(f"Processing {len(self.messages)} messages", extra={"tag": self.role})
                    if not self.messages:
                        self.update_poll_time(increase=True)
                    for msg in self.messages:
                        self.msg = msg
                        self.update_poll_time()
                        kb = None
                        if msg.act:
                            msg.short_url = config.url.deeplink.format(msg.act.uuid)
                            has_docs = len(msg.act.info.docs) > 1
                            kb = self.get_kb(has_docs=has_docs)
                            session.flush()
                        self.send_message(kb, disable_preview=(not msg.url_preview))
                        session.commit()
                log.info(
                    f"Finished sending messages, going to sleep for {self.poll_time} seconds",
                    extra={"tag": self.role}
                )
                pause.seconds(self.poll_time)
        except KeyboardInterrupt:
            log.info("Got KeyboardInterrupt, quitting", extra={"tag": self.role})
            sys.exit(0)

    def get_kb(self, has_docs=False):
        kb = telebot.types.InlineKeyboardMarkup(row_width=2)
        btn_layout = []
        if self.msg.user_id:
            btn_layout.append(
                telebot.types.InlineKeyboardButton(
                    self.templates["italian"]["keyboard"]["inline_buttons"]["details"],
                    callback_data=f"a.info:{self.msg.act.uuid}"
                )
            )
        else:
            btn_layout.append(
                telebot.types.InlineKeyboardButton(
                    self.templates["italian"]["keyboard"]["inline_buttons"]["details"],
                    url=self.msg.short_url,
                )
            )
            if has_docs:
                btn_layout.append(
                    telebot.types.InlineKeyboardButton(
                        self.templates["italian"]["keyboard"]["inline_buttons"]["docs"],
                        url=config.url.deeplink.format(f"docs-{self.msg.act.uuid}")
                    )
                )
        kb.add(*btn_layout)
        return kb

    def send_message(self, kb, disable_preview=False):
        attempts = 0
        dest = self.msg.user_id or self.msg.username
        while attempts <= self.attempts:
            try:
                attempts += 1
                result = self.bot.send_message(
                    text=self.msg.text,
                    chat_id=dest,
                    parse_mode="html",
                    reply_markup=kb,
                    disable_web_page_preview=disable_preview
                )
            except Exception as e:
                self.msg.error = repr(e)
                log.exception(f"Error while sending message {self.msg}", extra={"tag": self.role})
                pause.milliseconds(5000 * attempts)
            else:
                self.msg.sent = True
                self.msg.sent_at = dt.datetime.now()
                self.msg.message_id = result.message_id
                self.msg.chat_id = result.chat.id
                log.info(f"Successfully sent message {self.msg}", extra={"tag": self.role})
                pause.milliseconds(3000)
                break

    def delete_message(self, message_id: int):
        with SessionFactory() as session:
            result = session.get(Message, message_id)
            if not result:
                raise Exception("Message not found")
            try:
                self.bot.delete_message(chat_id=result.chat_id, message_id=result.message_id)
                result.deleted = True
                session.commit()
                log.info(f"Deleted message: {message_id}", extra={"tag": "DB"})
            except Exception:
                log.error(f"Error while deleting message: {message_id}", extra={"tag": "DB"})
