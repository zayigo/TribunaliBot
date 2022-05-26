# -*- coding: utf-8 -*-

import math
from typing import List, Union

import requests
from telebot import types
from database.database import SessionFactory

from database.models import Court, Tracking
from telegram.config import TelegramConfig

config = TelegramConfig.from_environ()

templates = requests.get(config.url.templates).json()


def split_list(lst, n: int):
    """Creates n-sized chunks from the given list
    Args:
        lst (List[Any]): List
        n (int): Size of chunks
    """
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def default_buttons() -> types.InlineKeyboardMarkup:
    """Generates persistent help keyboard"""
    kb = types.ReplyKeyboardMarkup(one_time_keyboard=False, resize_keyboard=True)
    kb.row(
        templates["italian"]["keyboard"]["buttons"]["add"],
        templates["italian"]["keyboard"]["buttons"]["list"],
    )
    kb.row(
        templates["italian"]["keyboard"]["buttons"]["cancel"],
        templates["italian"]["keyboard"]["buttons"]["help"],
    )
    return kb


def act_info(act):
    kb = types.InlineKeyboardMarkup(row_width=3)
    btn_layout = [
        types.InlineKeyboardButton(
            templates["italian"]["keyboard"]["inline_buttons"]["court"],
            callback_data=f"c.info:{act.court_id}:a.info:{act.uuid}",
        )
    ]
    if act.info.has_docs:
        btn_layout.append(
            types.InlineKeyboardButton(
                templates["italian"]["keyboard"]["inline_buttons"]["docs"],
                callback_data=f"a.docs:{act.info.id}:a.info:{act.uuid}",
            )
        )
    kb.add(*btn_layout)
    kb.add(
        types.InlineKeyboardButton(
            templates["italian"]["keyboard"]["inline_buttons"]["info"],
            callback_data=f"a.extra:{act.uuid}:a.info:{act.uuid}",
        )
    )
    return kb


def court_info(tracking, court_id, back: str = None):
    kb = types.InlineKeyboardMarkup(row_width=1)
    if tracking:
        kb.add(
            types.InlineKeyboardButton(
                templates["italian"]["keyboard"]["inline_buttons"]["delete"],
                callback_data=f"c.delete:{court_id}:{back}",
            )
        )
        if not tracking.track_all:
            kb.add(
                types.InlineKeyboardButton(
                    templates["italian"]["keyboard"]["inline_buttons"]["track_all"],
                    callback_data=f"c.track-all:{court_id}:{back}",
                )
            )
        else:
            kb.add(
                types.InlineKeyboardButton(
                    templates["italian"]["keyboard"]["inline_buttons"]["track_tlc"],
                    callback_data=f"c.track-tlc:{court_id}:{back}",
                )
            )
    else:
        kb.add(
            types.InlineKeyboardButton(
                templates["italian"]["keyboard"]["inline_buttons"]["add"],
                callback_data=f"c.add:{court_id}:{back}",
            )
        )
    if back:
        kb.add(
            types.InlineKeyboardButton(
                templates["italian"]["keyboard"]["inline_buttons"]["back"],
                callback_data=back,
            )
        )
    return kb


# region TOWN
def courts_list(
    courts: List[Court], action: str, user_id, back: str = None, row_width: int = 2
) -> types.InlineKeyboardMarkup:
    """Generates an InlineKeyboard from a list of courts"""
    kb = types.InlineKeyboardMarkup(row_width=row_width)
    btn_layout = []
    with SessionFactory() as session:
        for c in courts:
            is_tracking = session.get(Tracking, {"court_id": c.id, "user_id": user_id})
            emoji = "✅" if is_tracking else "❌"
            payload = f"{action}:{c.id}"
            if back:
                payload += f":{back}"
            button = types.InlineKeyboardButton(
                f"{emoji} {c.name}", callback_data=payload
            )
            btn_layout.append(button)
        for b in list(split_list(btn_layout, row_width)):
            kb.add(*b)
        return kb


def trackings_list(
    courts,
    count,
    action: str,
    back: str,
    user_id,
    page: int = 0,
) -> Union[bool, types.InlineKeyboardMarkup]:
    if not courts:
        return None
    kb = courts_list(courts=courts, action=action, back=back, user_id=user_id)
    last_page = int(math.ceil(count // 12))
    if page == last_page and page == 0:
        return kb
    # print(f"page: {page} - len {last_page}")
    if page == 0:
        kb.add(
            types.InlineKeyboardButton(
                templates["italian"]["keyboard"]["inline_buttons"]["p_next"],
                callback_data="l.page:next",
            )
        )
    elif page == last_page:
        kb.add(
            types.InlineKeyboardButton(
                templates["italian"]["keyboard"]["inline_buttons"]["p_back"],
                callback_data="l.page:back",
            )
        )
    else:
        btn_layout = [
            types.InlineKeyboardButton("◀️", callback_data="l.page:back"),
            types.InlineKeyboardButton("▶️", callback_data="l.page:next:"),
        ]
        kb.add(*btn_layout)
    return kb


# endregion TOWN


def inline_help() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    btn_help = types.InlineKeyboardButton(
        templates["italian"]["keyboard"]["buttons"]["help"], callback_data="help"
    )
    btn_annulla = types.InlineKeyboardButton(
        templates["italian"]["keyboard"]["buttons"]["cancel"], callback_data="annulla"
    )
    kb.add(*[btn_help, btn_annulla])
    return kb


def force_reply():
    return types.ForceReply(selective=True)


def list_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    btn_help = types.InlineKeyboardButton(
        templates["italian"]["keyboard"]["buttons"]["list"], callback_data="c.list"
    )
    kb.add(btn_help)
    return kb


def docs_keyboard(docs, back: str):
    kb = types.InlineKeyboardMarkup(row_width=1)
    count = 1
    for d in docs:
        url = d.url_archive or d.url
        if d.type.name == "web":
            emoji = "🔗"
            title = "Dettagli"
        else:
            emoji = "📄"
            title = d.title or f"Documento {count}"
            count += 1
        kb.add(types.InlineKeyboardButton(f"{emoji}  {title}", url=url))
    kb.add(
        types.InlineKeyboardButton(
            templates["italian"]["keyboard"]["inline_buttons"]["back"],
            callback_data=back,
        )
    )
    return kb
