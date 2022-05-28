# -*- coding: utf-8 -*-

import html
import re

import requests
import telebot  # type: ignore
from telebot import apihelper, types

from database.database import SessionFactory
from database.models import Act, Court, Doc, Message, Tracking, User, UserReport
from logger.logger import log
from telegram.config import TelegramConfig
from telegram.src import markups

config = TelegramConfig.from_environ()

apihelper.ENABLE_MIDDLEWARE = True

bot = telebot.TeleBot(config.main.token)

hideBoard = types.ReplyKeyboardRemove()

templates = requests.get(config.url.templates).json()

START_ACT = r"(?<=/start )\w{16,}"
START_DOCS = r"(?<=/start docs-)\w{16,}"


def get_match_from_message(text, regex):
    return match[0] if (match := re.search(regex, text)) else None


@bot.middleware_handler(update_types=['message'])
def set_user_message(bot_instance, m):
    with SessionFactory() as session:
        m.user = User.get_or_create(
            session,
            id=m.from_user.id,
            username=m.from_user.username,
            firstname=m.from_user.first_name,
            lastname=m.from_user.last_name,
            language=m.from_user.language_code,
        )


@bot.middleware_handler(update_types=['callback_query'])
def set_user_call(bot_instance, call):
    call_data = call.data.split(":")
    call.payload = call.data
    call.action = call_data[0]
    try:
        call.data = call_data[1] if "|" not in call_data[1] else call_data[1].split("|")
    except IndexError:
        call.data = None
    call.back = ":".join(call_data[2:]) or None
    if call.back == "None":
        call.back = None
    log.info(f"Got call with action:'{call.action}' - data:'{call.data}' - back:'{call.back}'", extra={"tag": "TG"})
    with SessionFactory() as session:
        call.user = User.get_or_create(
            session,
            id=call.from_user.id,
            username=call.from_user.username,
            firstname=call.from_user.first_name,
            lastname=call.from_user.last_name,
            language=call.from_user.language_code,
        )


@bot.message_handler(commands=["debug"])
def debug(m):
    with SessionFactory() as session:
        text = templates["italian"]["messages"]["debug"].format(user=html.escape(str(m.user)))
        Message.create(session, username=config.support.chat_id, text=text, priority=1000)


@bot.message_handler(commands=["annulla"])
@bot.message_handler(func=lambda m: m.text == templates["italian"]["keyboard"]["buttons"]["cancel"])
def cancel(m):
    """ Resets to default state """
    bot.reply_to(
        text=templates["italian"]["messages"]["cancel"],
        message=m,
        parse_mode="html",
        reply_markup=markups.default_buttons()
    )
    with SessionFactory() as session:
        User.update_by_id(session, id_=m.user.id, dct={"page": 0, "state": 0})


@bot.message_handler(commands=["help"])
@bot.message_handler(func=lambda m: m.text == templates["italian"]["keyboard"]["buttons"]["help"])
def help_prompt(m):
    """ Sends help message """
    with SessionFactory() as session:
        User.update_by_id(session, id_=m.user.id, dct={"state": 0})
    commands = "".join(f"\n• /{k} - {v}" for k, v in templates["italian"]["commands"].items())
    text = templates["italian"]["messages"]["help"].format(
        commands=commands, channel_name=config.channel.name, donation_url=config.url.donate
    )
    bot.reply_to(
        text=text, message=m, parse_mode="html", disable_web_page_preview=True, reply_markup=markups.default_buttons()
    )


# region START
@bot.message_handler(commands=["start"], regexp=START_ACT)
@bot.callback_query_handler(func=lambda call: True and call.action == "a.info")
def send_act_info(m):
    try:
        # message already in chat
        uuid = m.data
        bot.answer_callback_query(m.id)
        edit = True
    except AttributeError:
        # deeplink from channel
        uuid = get_match_from_message(m.text, START_ACT)
        edit = False
    with SessionFactory() as session:
        User.update_by_id(session, id_=m.user.id, dct={"state": 0})
        if act := Act.get_by_uuid(session, uuid=uuid):
            text = act.get_telegram_text()
            kb = markups.act_info(act)
            if edit:
                bot.edit_message_text(
                    text=text,
                    chat_id=m.user.id,
                    message_id=m.message.id,
                    parse_mode="html",
                    reply_markup=kb,
                    disable_web_page_preview=True
                )
            else:
                bot.send_message(
                    text=text, chat_id=m.chat.id, parse_mode="html", reply_markup=kb, disable_web_page_preview=True
                )
        else:
            bot.send_message(
                text=templates["italian"]["errors"]["act_not_found"],
                chat_id=m.chat.id,
                parse_mode="html",
                reply_markup=markups.default_buttons()
            )


@bot.callback_query_handler(func=lambda call: True and call.action == "c.info")
def court_info(m):
    court_id = m.data
    call_answer = templates["italian"]["answers"]["court_info"]
    bot.answer_callback_query(m.id, text=call_answer)
    with SessionFactory() as session:
        court = session.get(Court, court_id)
        text = templates["italian"]["messages"]["court_info"].format(
            court_name=court.name,
            user_count=court.user_count,
            act_count=court.act_count,
            act_count_tlc=court.act_count_tlc,
        )
        tracking = Tracking.get(session, user_id=m.user.id, court_id=court_id)
    kb = markups.court_info(tracking=tracking, court_id=court_id, back=m.back)
    bot.edit_message_text(
        text=text,
        chat_id=m.user.id,
        message_id=m.message.id,
        parse_mode="html",
        reply_markup=kb,
        disable_web_page_preview=True
    )


@bot.message_handler(commands=["start"], regexp=START_DOCS)
@bot.callback_query_handler(func=lambda call: True and call.action == "a.docs")
def info_docs(call):
    try:
        # message already in chat
        uuid = call.data
        call_answer = templates["italian"]["answers"]["docs"]
        bot.answer_callback_query(call.id, text=call_answer)
        edit = True
    except AttributeError:
        # deeplink from channel
        uuid = get_match_from_message(call.text, START_DOCS)
        edit = False
        call.back = f"a.info:{uuid}"
    with SessionFactory() as session:
        if edit:
            info_id = call.data
        else:
            act = Act.get_by_uuid(session, uuid=uuid)
            if not act:
                bot.send_message(
                    text=templates["italian"]["errors"]["act_not_found"],
                    chat_id=call.chat.id,
                    parse_mode="html",
                    reply_markup=markups.default_buttons()
                )
                return
            info_id = act.info_id
            tg_text = act.get_telegram_text()
        kb = markups.docs_keyboard(docs=Doc.get_by_info_id(session, info_id=info_id), back=call.back)
    if edit:
        bot.edit_message_text(
            text=call.message.html_text,
            chat_id=call.message.chat.id,
            message_id=call.message.id,
            parse_mode="html",
            reply_markup=kb,
            disable_web_page_preview=True
        )
    else:
        bot.send_message(
            text=tg_text, chat_id=call.chat.id, parse_mode="html", reply_markup=kb, disable_web_page_preview=True
        )


@bot.message_handler(commands=["start"])
def welcome(m):
    """ Sends welcome message to new users """
    if m.user.state == -1:
        text = templates["italian"]["messages"]["welcome"].format(
            user_name=m.user.firstname, bot_name=config.main.name
        )
        bot.reply_to(text=text, message=m, parse_mode="html")
        text = templates["italian"]["messages"]["welcome_2"]
        bot.send_message(text=text, chat_id=m.chat.id, parse_mode="html", reply_markup=markups.default_buttons())
        with SessionFactory() as session:
            User.update_by_id(session, id_=m.user.id, dct={"state": 0})
    else:
        text = templates["italian"]["errors"]["started"]
        bot.reply_to(text=text, message=m, parse_mode="html", reply_markup=markups.default_buttons())


# endregion START

# region ACT


@bot.callback_query_handler(func=lambda call: True and call.action == "a.extra")
def info_extra(call):
    call_answer = templates["italian"]["answers"]["extra"]
    bot.answer_callback_query(call.id, text=call_answer)
    with SessionFactory() as session:
        act = Act.get_by_uuid(session, uuid=call.data)
        dct_info = [f"• {k.replace('_', ' ').capitalize()}: <code>{v}</code>" for k, v in act.info.extra_info.items()]
        isp_text = ""
        if act.info.isp:
            isp_list = [isp.title() for isp in act.info.isp.keys()]
            isp_text = "\n• ISP: <code>" + ", ".join(isp_list) + "</code>"
        text = templates["italian"]["messages"]["extra_info"].format(
            dct_info="\n".join(dct_info), is_tlc=str(act.is_tlc), isp=isp_text
        )
        hide_report = bool(UserReport.get_by_id(session, user_id=call.user.id, act_id=act.id))
    kb = types.InlineKeyboardMarkup(row_width=1)
    if not hide_report:
        kb.add(
            types.InlineKeyboardButton(
                templates["italian"]["keyboard"]["inline_buttons"]["report"],
                callback_data=f"a.report:{call.data}:{call.back}"
            )
        )
    kb.add(
        types.InlineKeyboardButton(
            templates["italian"]["keyboard"]["inline_buttons"]["back"], callback_data=call.back
        )
    )
    bot.edit_message_text(
        text=text, chat_id=call.message.chat.id, message_id=call.message.id, parse_mode="html", reply_markup=kb
    )


@bot.callback_query_handler(func=lambda call: True and call.action == "a.report")
def report_error(call):
    with SessionFactory() as session:
        act = Act.get_by_uuid(session, uuid=call.data)
        result = UserReport.create(session, user_id=call.user.id, act_id=act.id)
        deeplink = config.main.deeplink.format(act.uuid)
        text = templates["italian"]["messages"]["report_admin"].format(
            user_id=call.user.id,
            username=html.escape(call.user.username),
            act=html.escape(str(act)),
            deeplink=deeplink
        )
        Message.create(session, username=config.support.chat_id, text=text, priority=1000)
    text = templates["italian"]["messages"]["report-error"] if result else templates["italian"]["messages"]["report"]
    # if not act.is_tlc:
    #     text += "\n\n" + templates["italian"]["messages"]["report_track_all"]
    bot.answer_callback_query(call.id, text=text, show_alert=True)
    info_extra(call)


# endregion ACT


@bot.callback_query_handler(func=lambda call: True and call.action == "c.list")
@bot.message_handler(commands=["lista"])
@bot.message_handler(commands=["aggiungi"])
@bot.message_handler(func=lambda m: m.text == templates["italian"]["keyboard"]["buttons"]["add"])
@bot.message_handler(func=lambda m: m.text == templates["italian"]["keyboard"]["buttons"]["list"])
def court_list(m):
    with SessionFactory() as session:
        User.update_by_id(session, id_=m.user.id, dct={"state": 0})
        courts, count = Tracking.paginate(session, page=m.user.page, page_size=12)
        try:
            # if user pressed back button from court info
            edit = bool(m.action)
            call_answer = templates["italian"]["answers"]["back"]
            bot.answer_callback_query(m.id, text=call_answer)
        except AttributeError:
            m.user.page = 0
            User.update_by_id(session, id_=m.user.id, dct={"page": 0})
            bot.send_chat_action(m.chat.id, "typing")
            edit = False
    # c.info:town.info:c.list
    kb = markups.trackings_list(
        courts=courts, count=count, action="c.info", back="c.list", page=m.user.page, user_id=m.user.id
    )
    text = templates["italian"]["messages"]["court_add"]
    if edit:
        bot.edit_message_text(
            text=text, chat_id=m.message.chat.id, message_id=m.message.id, parse_mode="html", reply_markup=kb
        )
    else:
        bot.send_message(text=text, chat_id=m.chat.id, reply_markup=kb)


@bot.callback_query_handler(func=lambda call: True and call.action == "l.page")
def court_page_change(call):
    bot.answer_callback_query(call.id)
    if call.data == "next":
        call.user.page += 1
    elif call.data == "back":
        call.user.page -= 1
    with SessionFactory() as session:
        User.update_by_id(session, id_=call.user.id, dct={"page": call.user.page})
        courts, count = Tracking.paginate(session, page=call.user.page, page_size=12)
    kb = markups.trackings_list(
        courts=courts, count=count, action="c.info", back="c.list", page=call.user.page, user_id=call.user.id
    )
    bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.id, reply_markup=kb)


@bot.callback_query_handler(func=lambda call: call.action == "c.add")
def court_add_select(call):
    with SessionFactory() as session:
        court, is_dup = Tracking.create(session, user_id=call.user.id, court_id=call.data)
    text = templates["italian"]["messages"]["track_tlc"]
    bot.answer_callback_query(call.id, text=text, show_alert=True)
    court_info(call)


@bot.callback_query_handler(func=lambda call: True and call.action == "c.delete")
def court_delete(call):
    with SessionFactory() as session:
        result = Tracking.delete(session, user_id=call.user.id, court_id=call.data)
        court = session.get(Court, call.data)
    text = templates["italian"]["messages"]["court_delete"]
    bot.answer_callback_query(call.id, text=text, show_alert=True)
    court_info(call)


@bot.callback_query_handler(func=lambda call: True and call.action == "c.track-all")
@bot.callback_query_handler(func=lambda call: True and call.action == "c.track-tlc")
def court_update(call):
    new_state = call.action == "c.track-all"
    with SessionFactory() as session:
        Tracking.update(session, user_id=call.user.id, court_id=call.data, new_state=new_state)
        if new_state:
            court = session.get(Court, call.data)
            text = templates["italian"]["messages"]["track_all"].format(court_name=court.name)
        else:
            text = templates["italian"]["messages"]["track_tlc"]
    bot.answer_callback_query(call.id, text=text, show_alert=True)
    court_info(call)


@bot.message_handler(func=lambda m: True)
def error_handling(m):
    bot.reply_to(text=templates["italian"]["errors"]["generic"], message=m, parse_mode="html")
