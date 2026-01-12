from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import Config


def kb_step_1() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.add(
        InlineKeyboardButton(text="🎁", callback_data="gift_1"),
        InlineKeyboardButton(text="🎁", callback_data="gift_2"),
        InlineKeyboardButton(text="🎁", callback_data="gift_3"),
    )
    b.adjust(3)
    return b.as_markup()


def kb_step_3() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывести бонус", callback_data="withdraw")]
    ])


def kb_step_4(opened_key: str | None = None) -> InlineKeyboardMarkup:
    """
    Юзер видит только:
      - Вступить в канал #1, #2...
      - ✅ Я подписался

    Если opened_key передан — соответствующая кнопка становится URL-кнопкой
    (без новых сообщений).
    """
    rows = []
    for i, ch in enumerate(Config.CHANNELS, start=1):
        if opened_key == ch.key:
            # после первого клика превращаем кнопку в URL
            rows.append([InlineKeyboardButton(text=f"Вступить в канал #{i}", url=ch.url)])
        else:
            rows.append([InlineKeyboardButton(text=f"Вступить в канал #{i}", callback_data=f"open_channel:{ch.key}")])

    rows.append([InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subs")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_step_5() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Продолжить", callback_data="to_nick")]
    ])


def kb_step_7_confirm_nick() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="nick_ok")],
        [InlineKeyboardButton(text="✏️ Указать другой ник", callback_data="nick_edit")],
    ])


def kb_app_created() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на наш канал", url=Config.MAIN_CHANNEL_URL)],
        [
            InlineKeyboardButton(text="👤 Мой профиль", callback_data="open_profile"),
            InlineKeyboardButton(text="🤝 Моя реф. система", callback_data="open_ref"),
        ]
    ])


def kb_profile() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤝 Реферальная система", callback_data="open_ref")]
    ])


def kb_ref_system() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data="copy_ref")],
        [InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="open_profile")]
    ])