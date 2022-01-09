import enum
from typing import Any, Dict

from sqlalchemy import (  # type: ignore
    Boolean,
    Column,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Time,
    and_,
    exists,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, MONEY, SMALLINT, TEXT, TIMESTAMP
from sqlalchemy.dialects.postgresql.ranges import TSTZRANGE  # type: ignore
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import backref, column_property, declarative_base, relationship
from sqlalchemy.orm.exc import DetachedInstanceError
from sqlalchemy.sql.expression import true
from sqlalchemy.sql.sqltypes import BigInteger

Base = declarative_base()

from database.utils import (UserReportHelper, TrackingHelper, ActHelper, UserHelper, DocHelper, MessageHelper)


class ReprBase():
    def __repr__(self) -> str:
        return self._repr(id=self.id)

    def _repr(self, **fields: Dict[str, Any]) -> str:
        '''
        Helper for __repr__
        '''
        field_strings = []
        at_least_one_attached_attribute = False
        for key, field in fields.items():
            try:
                field_strings.append(f'{key}={field!r}')
            except DetachedInstanceError:
                field_strings.append(f'{key}=DetachedInstanceError')
            else:
                at_least_one_attached_attribute = True
        if at_least_one_attached_attribute:
            return f"<{self.__class__.__name__}({','.join(field_strings)})>"
        return f"<{self.__class__.__name__} {id(self)}>"


class MixinSearch:
    @classmethod
    def fulltext_search(cls, session, search_string, field):
        return session.query(cls). \
            filter(func.to_tsvector('italian', getattr(cls, field))
                   .match(search_string, postgresql_regconfig='italian')).all()


class Platforms(enum.Enum):
    telegram = 1
    web = 2


class UserReport(ReprBase, UserReportHelper, Base):
    __tablename__ = "reports"

    # many to one - User -> Reports
    user_id = Column(BigInteger, ForeignKey('users.id'), primary_key=True)
    user = relationship("User", back_populates="reports", cascade="save-update")
    # many to one - Act -> Reports
    act_id = Column(Integer, ForeignKey('acts.id'), primary_key=True)
    act = relationship("Act", back_populates="reports", cascade="save-update")
    platform = Column(Enum(Platforms, validate_strings=True), nullable=False, default="telegram")
    processed = Column(Boolean, default=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return self._repr(
            user_id=self.user_id,
            user=self.user,
            act_id=self.act_id,
            act=self.act,
            platform=self.platform,
            processed=self.processed,
            timestamp=self.timestamp
        )


class Tracking(ReprBase, TrackingHelper, Base):
    __tablename__ = "trackings"

    user_id = Column(BigInteger, ForeignKey('users.id'), primary_key=True)
    user = relationship("User", back_populates="trackings", cascade="save-update")
    court_id = Column(String(6), ForeignKey('courts.id'), primary_key=True)
    court = relationship("Court", back_populates="users", cascade="save-update")
    track_all = Column(Boolean, default=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return self._repr(
            user_id=self.user_id,
            user=self.user,
            court_id=self.court_id,
            court=self.court,
            track_all=self.track_all,
            timestamp=self.timestamp
        )


class Act(MixinSearch, ReprBase, ActHelper, Base):
    __tablename__ = "acts"

    id = Column(Integer, primary_key=True)
    uuid = Column(String, unique=True)
    uuid_hr = Column(String, nullable=False, unique=True)
    # many to one - Court -> Acts
    court_id = Column(String(6), ForeignKey('courts.id'), nullable=False, index=True)
    court = relationship("Court", back_populates="acts", cascade="save-update")
    # one to one - Act -> ActInfo
    info_id = Column(Integer, ForeignKey('acts-info.id'), nullable=False)
    info = relationship(
        "ActInfo",
        backref=backref("Act", uselist=False, single_parent=True, cascade="save-update, all, delete-orphan")
    )
    # one to many - Act -> Messages
    messages = relationship("Message", back_populates="act")
    # one to many - Act -> Reports
    reports = relationship("UserReport", back_populates="act")
    text = Column(TEXT, nullable=False)
    full_text = Column(TEXT, nullable=False)
    is_tlc = Column(Boolean, default=False)
    date = Column(Date, index=True, nullable=False)
    notify = Column(Boolean, default=False)
    processed_at = Column(TIMESTAMP(timezone=True), index=True)
    process_time = Column(Time, nullable=True)
    error = Column(String, index=True)
    timestamp = Column(TIMESTAMP(timezone=True), index=True, nullable=False, server_default=func.now())

    def __repr__(self):
        return self._repr(
            id=self.id,
            uuid=self.uuid,
            uuid_hr=self.uuid_hr,
            info_id=self.info_id,
            court_id=self.court_id,
            is_tlc=self.is_tlc,
            text=self.text,
            date=self.date,
        )


class Court(ReprBase, Base):
    __tablename__ = "courts"

    # istat code
    id = Column(String(6), primary_key=True)
    name = Column(String, nullable=False, index=True)
    raw_name = Column(String, nullable=False, index=True)
    # one to many - Court -> acts
    acts = relationship("Act", back_populates="court", cascade="save-update")
    act_count = column_property(select([func.count(Act.id)]).where(Act.court_id == id).scalar_subquery(), deferred=True)
    act_count_tlc = column_property(
        select([func.count(Act.id)]).where(and_(Act.court_id == id, Act.is_tlc == true())).scalar_subquery(),
        deferred=True
    )
    # many to many - Courts -> Users
    users = relationship("Tracking", back_populates="court", cascade="all, delete-orphan")
    is_active_tlc = column_property(exists().where(and_(Act.court_id == id, Act.is_tlc == true())), deferred=True)

    def __repr__(self):
        return self._repr(
            id=self.id,
            name=self.name,
            raw_name=self.raw_name,
        )


class DocType(enum.Enum):
    text = 1
    web = 2
    other = 3


class Doc(MixinSearch, ReprBase, DocHelper, Base):
    __tablename__ = "docs"

    id = Column(Integer, primary_key=True)
    # many to one - ActInfo > Doc - no reverse
    info_id = Column(Integer, ForeignKey('acts-info.id'), index=True, nullable=False)
    info = relationship("ActInfo", back_populates="docs", cascade="save-update")
    title = Column(String)
    type = Column(Enum(DocType, validate_strings=True))
    url = Column(String, nullable=False)
    url_archive = Column(String)
    ocr = Column(TEXT)
    is_working = Column(Boolean, index=True)  # default=False
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, index=True, server_default=func.now())

    def __repr__(self):
        return self._repr(
            id=self.id,
            info_id=self.info_id,
            info=self.info,
            url=self.url,
            type=self.type,
            url_archive=self.url_archive,
            is_working=self.is_working
        )


class ActInfo(ReprBase, Base):
    __tablename__ = "acts-info"

    id = Column(Integer, primary_key=True)
    matches = Column(MutableDict.as_mutable(JSONB))  # default=dict
    blacklist = Column(MutableDict.as_mutable(JSONB))  # default=dict
    isp = Column(MutableDict.as_mutable(JSONB), index=True)  # default=dict
    extra_info = Column(MutableDict.as_mutable(JSONB), default=dict)
    ai_info = Column(MutableDict.as_mutable(JSONB), default=dict)
    # one to many - ActInfo > Doc
    docs = relationship("Doc", back_populates="info", cascade="all, delete-orphan")
    has_docs = column_property(exists().where(Doc.info_id == id))
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return self._repr(
            id=self.id,
            matches=self.matches,
            blacklist=self.blacklist,
            isp=self.isp,
            extra_info=self.extra_info,
            docs=self.docs
        )


class InteractionTypes(enum.Enum):
    message = 1
    command = 2
    button = 3


class Interaction(ReprBase, Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True)
    platform = Column(Enum(Platforms, validate_strings=True), nullable=False, default="telegram")
    type = Column(Enum(InteractionTypes, validate_strings=True), nullable=False)
    text = Column(String)
    # many to one - User -> Interactions
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False, index=True)
    user = relationship("User", back_populates="interactions", cascade="save-update")
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return self._repr(
            id=self.id, platform=self.platform, type=self.type, text=self.text, user_id=self.user_id, user=self.user
        )


class PaymentReasons(enum.Enum):
    first = 1
    renew = 2
    other = 3


class Payment(ReprBase, Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    amount = Column(MONEY, nullable=False)
    reason = Column(Enum(PaymentReasons, validate_strings=True), nullable=False)
    email = Column(String, nullable=False, index=True)
    # many to one - User -> Payments
    user_id = Column(BigInteger, ForeignKey('users.id'), index=True, nullable=False)
    user = relationship("User", back_populates="payments", cascade="save-update")
    # many to one - Subscription -> Payments
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=True)
    subscription = relationship("Subscription", back_populates="payments", cascade="save-update")
    timestamp = Column(TIMESTAMP(timezone=True), index=True, nullable=False, server_default=func.now())

    def __repr__(self):
        return self._repr(
            id=self.id,
            amount=self.amount,
            reason=self.reason,
            email=self.email,
            user_id=self.user_id,
            user=self.user,
            subscription_id=self.subscription_id,
            subscription=self.subscription
        )


class Subscription(ReprBase, Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    # many to one - User -> Subscriptions
    user_id = Column(BigInteger, ForeignKey('users.id'), index=True, nullable=False)
    user = relationship("User", back_populates="subscriptions", cascade="save-update")
    period = Column(TSTZRANGE, nullable=False, index=True)
    # one to many - Subscription -> Payments
    payments = relationship("Payment", back_populates="subscription", cascade="save-update")
    times_extended = column_property(
        select([func.count(Payment.id)]).where(Payment.subscription_id == id).scalar_subquery(), deferred=True
    )

    def __repr__(self):
        return self._repr(id=self.id, user_id=self.user_id, user=self.user, period=self.period)


class User(ReprBase, UserHelper, Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    username = Column(String, index=True)
    firstname = Column(String)
    lastname = Column(String)
    language = Column(String(4))
    state = Column(SMALLINT, default=-1)
    page = Column(SMALLINT, default=0)
    is_premium = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False, index=True)
    is_banned = Column(Boolean, default=False, index=True)
    # many to many - Courts -> Users"
    trackings = relationship("Tracking", back_populates="user", cascade="all, delete-orphan")
    has_trackings = column_property(exists().where(Tracking.user_id == id), deferred=True)
    courts = association_proxy("trackings", "court")
    # many to one - User -> Payments
    payments = relationship("Payment", back_populates="user", cascade="save-update")
    # one to many - User -> Interactions
    interactions = relationship("Interaction", back_populates="user", cascade="all, delete-orphan")
    # one to many - User -> Messages
    messages = relationship("Message", back_populates="user", cascade="save-update")
    # one to many - User -> Subscriptions
    subscriptions = relationship("Subscription", back_populates="user", cascade="save-update")
    # one to many - User -> Reports
    reports = relationship("UserReport", back_populates="user", cascade="all, delete-orphan")
    first_message = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    last_update = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.current_timestamp())

    @hybrid_property
    def fullname(self):
        if self.firstname is not None:
            return self.firstname + " " + self.lastname
        return self.lastname

    def __repr__(self):
        return self._repr(
            id=self.id,
            username=self.username,
            firstname=self.firstname,
            lastname=self.lastname,
            language=self.language,
            state=self.state,
            page=self.page,
            is_premium=self.is_premium,
            is_admin=self.is_admin,
            is_banned=self.is_banned,
            first_message=self.first_message
        )


class Message(ReprBase, MessageHelper, Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    # many to one - User -> Messages
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=True)
    user = relationship("User", back_populates="messages", cascade="save-update")
    # many to one - Act -> Messages
    act_id = Column(Integer, ForeignKey('acts.id'), nullable=True)
    act = relationship("Act", back_populates="messages", cascade="save-update")
    text = Column(String, nullable=False)
    url_preview = Column(Boolean, default=True, nullable=False)
    short_url = Column(String)
    sent = Column(Boolean, default=False, index=True)
    deleted = Column(Boolean, default=False, index=True)
    error = Column(String)
    username = Column(String)
    sent_at = Column(TIMESTAMP(timezone=True))
    message_id = Column(Integer)
    chat_id = Column(BigInteger)
    priority = Column(Integer, index=True, default=0)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return self._repr(
            id=self.id,
            user=self.user,
            user_id=self.user_id,
            act_id=self.act_id,
            text=self.text,
            url_preview=self.url_preview,
            short_url=self.short_url,
            sent=self.sent,
            error=self.error,
            username=self.username,
            message_id=self.message_id,
            chat_id=self.chat_id,
            priority=self.priority
        )


Court.has_users = column_property(
    exists().where(Tracking.court_id == Court.id).correlate_except(Tracking), deferred=True
)
Court.user_count = column_property(
    select([func.count(Tracking.user_id)]).where(Tracking.court_id == Court.id
                                                 ).correlate_except(Tracking).scalar_subquery(),
    deferred=True
)