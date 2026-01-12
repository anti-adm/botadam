from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Channel:
    key: str            # внутренний ключ (НЕ показывается юзеру)
    title: str          # текст кнопки
    url: str            # ссылка
    chat_id: int        # -100...
    is_private: bool    # True = закрытый (проверяем только клик), False = открытый (проверяем подписку)


class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

    # Пример:
    # is_private=True  -> закрытый канал, бот проверит только что юзер нажал кнопку
    # is_private=False -> открытый канал, бот проверит подписку через get_chat_member
    CHANNELS = [
        Channel(
            key="ch1",
            title="Вступить в канал #1",
            url="https://t.me/+yD07fdnLgts3M2Ey",
            chat_id=-1002967593081,
            is_private=True,
        ),
        # Channel(key="ch2", title="Вступить в канал #2", url="https://t.me/+xxxxx", chat_id=-100..., is_private=True),
    ]

    MAIN_CHANNEL_URL = "https://t.me/+yD07fdnLgts3M2Ey"

    ASSETS_DIR = BASE_DIR / "assets"
    IMG_STEP_1 = ASSETS_DIR / "step_1.png"
    IMG_STEP_2 = ASSETS_DIR / "step_2.png"
    IMG_STEP_3 = ASSETS_DIR / "step_3.png"
    IMG_STEP_4 = ASSETS_DIR / "step_4.png"
    IMG_STEP_5 = ASSETS_DIR / "step_5.png"
    IMG_STEP_6 = ASSETS_DIR / "step_6.png"
    IMG_STEP_7 = ASSETS_DIR / "step_7.png"
    IMG_STEP_8 = ASSETS_DIR / "step_8.png"
    IMG_STEP_9 = ASSETS_DIR / "step_9.png"

    TXT_STEP_1 = "Вам выпала уникальная возможность в раздаче, выберите один из трёх бонусов"
    TXT_STEP_3 = "🎉Поздравляем!\nВам начислен бонус: 25 000 РОБАКСОВ"
    TXT_STEP_4 = "Чтобы получить бонус, подпишитесь на каналы"
    TXT_STEP_5 = "✅ Подписка подтверждена"
    TXT_STEP_6 = "✍️ Укажите ваш никнейм в роблоксе, по нему будут отправлены робаксы"
    TXT_STEP_7 = "Ваш ник: <b>{nickname}</b>\nПодтвердить?"

    TXT_APP_CREATED = (
        "🎉 <b>Заявка успешно создана!</b>\n\n"
        "👤 Ник: <b>{nickname}</b>\n"
        "💰 Сумма: <b>25 000 RB</b>\n\n"
        "⏳ Статус: <b>{status}</b>"
    )

    TXT_PROFILE = (
        "👤 Никнейм: <b>{nickname}</b>\n"
        "⏳ Статус: <b>{status}</b>\n"
        "🤝 Мои рефералы: <b>{ref_count}</b>"
    )

    TXT_REF_SYSTEM = (
        "🤝 <b>Моя реферальная система</b>\n\n"
        "Мои рефералы: <b>{ref_count}</b>\n\n"
        "🔗 Ваша реферальная ссылка:\n"
        "<code>{ref_link}</code>"
    )

    ERR_WRONG_STEP = "⛔️ Нельзя перескочить шаги. Нажимайте кнопки в текущем сообщении."
    ERR_NOT_SUBSCRIBED = "❌ Вы не выполнили условия. Перейдите в каналы и нажмите «✅ Я подписался» ещё раз."
    ERR_CANT_CHECK = "⚠️ Не могу проверить подписку. Проверь права бота/тип канала и попробуй ещё раз."
    ERR_BAD_NICK = (
        "❌ Никнейм неверный.\n"
        "Разрешено: 3–20 символов, латиница/цифры/подчёркивание.\n"
        "Пример: Player_123"
    )