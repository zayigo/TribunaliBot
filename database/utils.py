import html

import requests
from hashids import Hashids
from sqlalchemy import and_, func, update
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import delete, true, false

from sqlalchemy.sql.sqltypes import Boolean

import database.models as models
from database.config import ActConfig
from logger.logger import log


class UserHelper:
    @classmethod
    def update_by_id(cls, session, id_: int, dct) -> Boolean:
        try:
            stmt = update(cls).where(cls.id == id_).values(dct)
            session.execute(stmt)
            session.commit()
            log.info(f"Updated user: {id_} -> {dct}", extra={"tag": "DB"})
            return True
        except Exception:
            log.exception(f"User update error: {id_} -> {dct}", extra={"tag": "DB"})
            return False

    @classmethod
    def get_or_create(cls, session, **kwargs):
        user = session.get(cls, kwargs.get("id"))
        if user:
            return user
        user = cls(**kwargs)
        try:
            session.add(user)
            session.commit()
        except Exception:
            log.exception(f"Error while saving {user}", extra={"tag": "DB"})
            session.rollback()
            return None
        else:
            return user

    @classmethod
    def get_admin_ids(cls, session):
        stmt = select(cls.id).where(cls.is_admin == true())
        return session.execute(stmt).scalars().all()


class TrackingHelper:
    @classmethod
    def get_users_id(cls, session, court_id: str, only_tlc=False):
        if only_tlc:
            stmt = (
                select(cls.user_id)
                .join(models.User)
                .where(and_(cls.court_id == court_id, models.User.is_banned == false()))
            )
        else:
            stmt = (
                select(cls.user_id)
                .join(models.User)
                .where(
                    and_(
                        cls.court_id == court_id,
                        cls.track_all == true(),
                        models.User.is_banned == false(),
                    )
                )
            )
        return session.execute(stmt).scalars().all()

    @classmethod
    def get(cls, session, user_id: int, court_id: str):
        stmt = select(cls).where(and_(cls.user_id == user_id, cls.court_id == court_id))
        return session.execute(stmt).scalar()

    @classmethod
    def get_by_user(cls, session, user_id: int):
        stmt = select(models.Court).join(cls).where(cls.user_id == user_id)
        return session.execute(stmt).scalars().all()

    @classmethod
    def update(cls, session, user_id: int, court_id: str, new_state):
        dct = {"track_all": new_state}
        stmt = (
            update(cls)
            .where(and_(cls.user_id == user_id, cls.court_id == court_id))
            .values(dct)
        )
        session.execute(stmt)
        session.commit()
        log.info(f"Updated tracking {user_id} -> {dct}", extra={"tag": "DB"})

    @classmethod
    def delete(cls, session, user_id: int, court_id: str):
        if not cls.get(session, user_id=user_id, court_id=court_id):
            return False
        stmt = delete(cls).where(and_(cls.user_id == user_id, cls.court_id == court_id))
        session.execute(stmt)
        log.info(f"Deleted tracking: {user_id} - {court_id}", extra={"tag": "DB"})
        session.commit()
        return True

    @classmethod
    def create(cls, session, user_id: int, court_id: str):
        stmt = select(cls).where(and_(cls.user_id == user_id, cls.court_id == court_id))
        result = session.execute(stmt).scalar()
        if result:
            court = result.court
            log.info(f"Duplicate tracking: {user_id} - {court}", extra={"tag": "DB"})
            return court, True
        tracking = cls(user_id=user_id, court_id=court_id)
        session.add(tracking)
        session.commit()
        log.info(
            f"New tracking added: {user_id} - {tracking.court}", extra={"tag": "DB"}
        )
        return tracking.court, False

    @classmethod
    def paginate(cls, session, page: int, page_size: int):
        stmt = (
            select(models.Court)
            .limit(page_size)
            .offset(page * page_size)
            .order_by(models.Court.name)
        )
        courts = session.execute(stmt).scalars().all()
        stmt = select(func.count(models.Court.id))
        count = session.execute(stmt).scalar()
        return courts, count


class ActHelper:

    config = ActConfig.from_environ()
    hash_ = (
        Hashids(salt=config.hash_secret, min_length=16) if config.hash_secret else None
    )
    templates = (
        requests.get(config.url.templates, timeout=60).json()
        if config.url.templates
        else []
    )

    @classmethod
    def get_info_id(cls, session, uuid: str):
        stmt = select(cls.info_id).where(cls.uuid == uuid)
        return session.execute(stmt).scalar()

    @classmethod
    def get_by_uuid_hr(cls, session, uuid_hr: str):
        stmt = select(cls).where(cls.uuid_hr == uuid_hr)
        return session.execute(stmt).scalar()

    @classmethod
    def get_by_uuid(cls, session, uuid: str):
        stmt = select(cls).where(cls.uuid == uuid).options(joinedload(cls.court))
        return session.execute(stmt).scalar()

    def set_properties(self):
        self.uuid = ActHelper.hash_.encode(self.id)

    def get_telegram_text(self):
        text = ActHelper.templates["italian"]["messages"]["template"].format(
            tribunale=self.court.name.upper(),
            sezione=self.info.extra_info["sezione"].upper(),
            tipo=self.info.extra_info["tipo"].title().replace(" ", ""),
            date=self.date.strftime("%d/%m/%Y"),
            text=html.escape(self.text),
        )
        if self.info.isp:
            text += "\n\n"
            for isp in self.info.isp:
                text += f"#{isp.replace(' ', '')} "
        return text


class UserReportHelper:
    @classmethod
    def get_by_id(cls, session, user_id: int, act_id: int):
        return session.get(cls, {"user_id": user_id, "act_id": act_id})

    @classmethod
    def create(cls, session, user_id: int, act_id: int, platform: str = "telegram"):
        if cls.get_by_id(session, user_id=user_id, act_id=act_id):
            return True
        session.add(cls(user_id=user_id, act_id=act_id, platform=platform))
        session.commit()
        return False


class MessageHelper:
    @classmethod
    def create(
        cls, session, text: str, user_id: int = None, username: str = "", priority=0
    ):
        msg = cls(text=text, priority=priority)
        if user_id:
            msg.user_id = user_id
        elif username:
            msg.username = username
        session.add(msg)
        session.commit()

    @classmethod
    def get_by_id(cls, session, id_: int):
        return session.get(cls, id_)

    @classmethod
    def get_by_tg_ids(cls, session, message_id: int, chat_id: int):
        stmt = select(cls).where(
            and_(cls.message_id == message_id, cls.chat_id == chat_id)
        )
        return session.execute(stmt).scalars().one()


class DocHelper:
    @classmethod
    def get_by_info_id(cls, session, info_id: int):
        stmt = select(cls).where(cls.info_id == info_id).order_by(cls.type)
        return session.execute(stmt).scalars().all()
