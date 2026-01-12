import asyncio
import logging
import re
from pathlib import Path
import html

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.types.input_file import FSInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import Config
from db import Database
from keyboards import (
    kb_step_1, kb_step_3, kb_step_4, kb_step_5,
    kb_step_7_confirm_nick, kb_app_created, kb_profile, kb_ref_system
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("bot")

db = Database("bot.sqlite3")
router = Router()

NICK_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


# ---------------- MEDIA ----------------
def _photo_or_none(path: Path) -> FSInputFile | None:
    p = Path(path)
    if p.exists() and p.is_file():
        return FSInputFile(p)
    return None


async def send_media(
    bot: Bot,
    chat_id: int,
    img_path: Path,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML",
):
    f = _photo_or_none(img_path)
    if f:
        return await bot.send_photo(
            chat_id,
            f,
            caption=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    return await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)


async def safe_delete(bot: Bot, chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest:
        pass


async def safe_answer(
    callback: CallbackQuery,
    text: str | None = None,
    show_alert: bool = False,
    url: str | None = None,
):
    try:
        await callback.answer(text=text, show_alert=show_alert, url=url)
    except TelegramBadRequest:
        pass


def _assets_check():
    missing = []
    for p in [
        Config.IMG_STEP_1, Config.IMG_STEP_2, Config.IMG_STEP_3, Config.IMG_STEP_4,
        Config.IMG_STEP_5, Config.IMG_STEP_6, Config.IMG_STEP_7, Config.IMG_STEP_8, Config.IMG_STEP_9
    ]:
        if not Path(p).exists():
            missing.append(str(p))
    if missing:
        log.warning("Missing assets:\n%s", "\n".join(missing))


# ---------------- BUSINESS LOGIC ----------------
def compute_status(ref_count: int) -> str:
    return "Ускорено" if ref_count >= 30 else "В обработке"


def get_channel_by_key(key: str):
    for ch in Config.CHANNELS:
        if ch.key == key:
            return ch
    return None


# ---------------- STEPS SENDERS ----------------
async def send_step_1(bot: Bot, chat_id: int, user_id: int):
    db.set_step(user_id, 1)
    await send_media(bot, chat_id, Config.IMG_STEP_1, Config.TXT_STEP_1, reply_markup=kb_step_1())


async def send_step_3(bot: Bot, chat_id: int, user_id: int):
    db.set_step(user_id, 3)
    await send_media(bot, chat_id, Config.IMG_STEP_2, Config.TXT_STEP_3, reply_markup=kb_step_3())


async def send_step_4(bot: Bot, chat_id: int, user_id: int):
    db.set_step(user_id, 4)
    await send_media(bot, chat_id, Config.IMG_STEP_4, Config.TXT_STEP_4, reply_markup=kb_step_4())


async def send_step_5(bot: Bot, chat_id: int, user_id: int):
    db.set_step(user_id, 5)
    await send_media(bot, chat_id, Config.IMG_STEP_5, Config.TXT_STEP_5, reply_markup=kb_step_5())


async def send_step_6(bot: Bot, chat_id: int, user_id: int):
    db.set_step(user_id, 6)
    await send_media(bot, chat_id, Config.IMG_STEP_6, Config.TXT_STEP_6)


async def send_step_7_confirm(bot: Bot, chat_id: int, user_id: int, nickname: str):
    db.set_step(user_id, 7)
    await send_media(
        bot,
        chat_id,
        Config.IMG_STEP_6,
        Config.TXT_STEP_7.format(nickname=html.escape(nickname)),
        reply_markup=kb_step_7_confirm_nick()
    )


async def send_application_created(bot: Bot, chat_id: int, user_id: int):
    user = db.get_user(user_id)
    nickname = user["nickname"] or "-"
    ref_count = int(user["referral_count"])
    status = compute_status(ref_count)

    db.set_status(user_id, status)
    db.set_applied(user_id, 1)
    db.set_step(user_id, 8)

    await send_media(
        bot,
        chat_id,
        Config.IMG_STEP_8,
        Config.TXT_APP_CREATED.format(nickname=html.escape(nickname), status=html.escape(status)),
        reply_markup=kb_app_created()
    )


async def send_profile(bot: Bot, chat_id: int, user_id: int):
    user = db.get_user(user_id)
    nickname = user["nickname"] or "-"
    ref_count = int(user["referral_count"])
    status = compute_status(ref_count)
    db.set_status(user_id, status)

    db.set_step(user_id, 100)
    await send_media(
        bot,
        chat_id,
        Config.IMG_STEP_9,
        Config.TXT_PROFILE.format(
            nickname=html.escape(nickname),
            status=html.escape(status),
            ref_count=ref_count
        ),
        reply_markup=kb_profile()
    )


async def send_ref_system(bot: Bot, chat_id: int, user_id: int):
    ref_count = db.get_referral_count(user_id)
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={user_id}"

    db.set_step(user_id, 101)
    await send_media(
        bot,
        chat_id,
        Config.IMG_STEP_7,
        Config.TXT_REF_SYSTEM.format(ref_count=ref_count, ref_link=html.escape(ref_link)),
        reply_markup=kb_ref_system()
    )


# ---------------- SUBS CHECK (open/private logic) ----------------
async def check_requirements(bot: Bot, user_id: int) -> bool | None:
    """
    True  -> всё выполнено
    False -> не выполнено
    None  -> не смогли проверить (ошибка/нет прав)
    """
    for ch in Config.CHANNELS:
        # 1) клик обязателен для всех (закрытый канал: только клик и проверяем)
        if not db.has_clicked_channel(user_id, ch.key):
            return False

        # 2) если канал открытый — проверяем подписку
        if not ch.is_private:
            try:
                member = await bot.get_chat_member(chat_id=ch.chat_id, user_id=user_id)
                if member.status in ("left", "kicked"):
                    return False
            except (TelegramForbiddenError, TelegramBadRequest):
                return None
            except Exception:
                return None

    return True


# ---------------- REF NOTIFY ----------------
async def notify_inviter_if_needed(bot: Bot, invited_id: int, invited_nickname: str):
    inviter_id = db.get_referral_inviter(invited_id)
    if not inviter_id:
        return
    if db.is_referral_notified(invited_id):
        return

    db.mark_referral_notified(invited_id, invited_nickname)

    try:
        await bot.send_message(
            inviter_id,
            f"✅ Ваш реферал успешно прошел регистрацию!\nНик реферала: <b>{html.escape(invited_nickname)}</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass


# ---------------- HANDLERS ----------------
@router.message(CommandStart())
async def on_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    db.ensure_user(user_id)

    # referral param: /start 123
    parts = (message.text or "").split(maxsplit=1)
    ref_id = None
    if len(parts) == 2:
        try:
            ref_id = int(parts[1])
        except ValueError:
            ref_id = None

    if ref_id and ref_id != user_id:
        db.ensure_user(ref_id)
        added = db.add_referral_once(invited_id=user_id, inviter_id=ref_id)
        if added:
            db.set_inviter(user_id, ref_id)

    # старт заново
    db.set_step(user_id, 0)
    db.set_applied(user_id, 0)
    db.set_nickname(user_id, None)
    db.set_status(user_id, "В обработке")
    db.reset_channel_clicks(user_id)

    await send_step_1(bot, message.chat.id, user_id)


@router.callback_query(F.data.in_({"gift_1", "gift_2", "gift_3"}))
async def on_gift(callback: CallbackQuery, bot: Bot):
    await safe_answer(callback)

    user_id = callback.from_user.id
    u = db.get_user(user_id)
    if not u or int(u["step"]) != 1:
        await safe_answer(callback, Config.ERR_WRONG_STEP, show_alert=True)
        return

    await safe_delete(bot, callback.message.chat.id, callback.message.message_id)
    await send_step_3(bot, callback.message.chat.id, user_id)


@router.callback_query(F.data == "withdraw")
async def on_withdraw(callback: CallbackQuery, bot: Bot):
    await safe_answer(callback)

    user_id = callback.from_user.id
    u = db.get_user(user_id)
    if not u or int(u["step"]) != 3:
        await safe_answer(callback, Config.ERR_WRONG_STEP, show_alert=True)
        return

    await safe_delete(bot, callback.message.chat.id, callback.message.message_id)
    await send_step_4(bot, callback.message.chat.id, user_id)


@router.callback_query(F.data.startswith("open_channel:"))
async def on_open_channel(callback: CallbackQuery, bot: Bot):
    key = callback.data.split(":", 1)[1]
    ch = get_channel_by_key(key)
    if not ch:
        await safe_answer(callback, "Канал не найден.", show_alert=True)
        return

    # фиксируем клик (важно для закрытых)
    db.mark_channel_clicked(callback.from_user.id, key)

    # превращаем нажатую кнопку в URL-кнопку (без новых сообщений)
    try:
        await bot.edit_message_reply_markup(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=kb_step_4(opened_key=key),
        )
    except TelegramBadRequest:
        pass

    # убираем "крутилку" и говорим нажать ещё раз
    await safe_answer(callback, "Нажми эту кнопку ещё раз — откроется канал ✅", show_alert=True)

    # открываем ссылку (ВАЖНО: не вызывать перед этим callback.answer() без url)
    await safe_answer(callback, url=ch.url)


@router.callback_query(F.data == "check_subs")
async def on_check_subs(callback: CallbackQuery, bot: Bot):
    await safe_answer(callback)

    user_id = callback.from_user.id
    u = db.get_user(user_id)
    if not u or int(u["step"]) != 4:
        await safe_answer(callback, Config.ERR_WRONG_STEP, show_alert=True)
        return

    res = await check_requirements(bot, user_id)
    if res is None:
        await safe_answer(callback, Config.ERR_CANT_CHECK, show_alert=True)
        return
    if res is False:
        await safe_answer(callback, Config.ERR_NOT_SUBSCRIBED, show_alert=True)
        return

    await safe_delete(bot, callback.message.chat.id, callback.message.message_id)
    await send_step_5(bot, callback.message.chat.id, user_id)


@router.callback_query(F.data == "to_nick")
async def on_to_nick(callback: CallbackQuery, bot: Bot):
    await safe_answer(callback)

    user_id = callback.from_user.id
    u = db.get_user(user_id)
    if not u or int(u["step"]) != 5:
        await safe_answer(callback, Config.ERR_WRONG_STEP, show_alert=True)
        return

    await safe_delete(bot, callback.message.chat.id, callback.message.message_id)
    await send_step_6(bot, callback.message.chat.id, user_id)


@router.message(F.text)
async def on_text(message: Message, bot: Bot):
    user_id = message.from_user.id
    db.ensure_user(user_id)
    u = db.get_user(user_id)

    if not u or int(u["step"]) != 6:
        return

    nickname = (message.text or "").strip()
    if not NICK_RE.fullmatch(nickname):
        await message.answer(Config.ERR_BAD_NICK, parse_mode="HTML")
        return

    db.set_nickname(user_id, nickname)
    await send_step_7_confirm(bot, message.chat.id, user_id, nickname)


@router.callback_query(F.data == "nick_edit")
async def on_nick_edit(callback: CallbackQuery, bot: Bot):
    await safe_answer(callback)

    user_id = callback.from_user.id
    u = db.get_user(user_id)
    if not u or int(u["step"]) != 7:
        await safe_answer(callback, Config.ERR_WRONG_STEP, show_alert=True)
        return

    await safe_delete(bot, callback.message.chat.id, callback.message.message_id)
    await send_step_6(bot, callback.message.chat.id, user_id)


@router.callback_query(F.data == "nick_ok")
async def on_nick_ok(callback: CallbackQuery, bot: Bot):
    await safe_answer(callback)

    user_id = callback.from_user.id
    u = db.get_user(user_id)
    if not u or int(u["step"]) != 7:
        await safe_answer(callback, Config.ERR_WRONG_STEP, show_alert=True)
        return

    await safe_delete(bot, callback.message.chat.id, callback.message.message_id)

    await send_application_created(bot, callback.message.chat.id, user_id)

    nickname = (db.get_user(user_id)["nickname"] or "").strip()
    if nickname:
        await notify_inviter_if_needed(bot, user_id, nickname)


@router.callback_query(F.data == "open_profile")
async def on_open_profile(callback: CallbackQuery, bot: Bot):
    await safe_answer(callback)
    await send_profile(bot, callback.message.chat.id, callback.from_user.id)


@router.callback_query(F.data == "open_ref")
async def on_open_ref(callback: CallbackQuery, bot: Bot):
    await safe_answer(callback)
    await send_ref_system(bot, callback.message.chat.id, callback.from_user.id)


@router.callback_query(F.data == "copy_ref")
async def on_copy_ref(callback: CallbackQuery, bot: Bot):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={callback.from_user.id}"
    await safe_answer(callback, f"Ваша ссылка:\n{link}", show_alert=True)

@router.callback_query()
async def fallback_cb(callback: CallbackQuery):
    log.warning("UNHANDLED CALLBACK: %s", callback.data)
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

# ---------------- RUN ----------------
async def main():
    if not Config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty. Create .env and set BOT_TOKEN=...")

    _assets_check()

    bot = Bot(token=Config.BOT_TOKEN)
    me = await bot.get_me()
    log.info("Bot started as @%s (id=%s)", me.username, me.id)
    log.info("Polling started. Press Ctrl+C to stop.")

    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())