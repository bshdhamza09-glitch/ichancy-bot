import asyncio
import logging
import os
import sqlite3
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, KeyboardButton, ReplyKeyboardMarkup, Message, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN', '').strip()
DB = Path(__file__).with_name('users.db')
router = Router()

# Custom emoji IDs must be obtained from Telegram and can be used only where supported.
# Regular emojis are the reliable fallback for all Telegram clients.
ROWS = [
    ['🟥 Ichancy'],
    ['💸 شحن رصيد البوت', '💰 سحب رصيد البوت'],
    ['💸 نظام الإحالات'],
    ['🎟️ إهداء رصيد', '🎁 كود هدية'],
    ['📝 رسالة للأدمن', '💌 تواصل معنا'],
    ['✅ السجل', '⚠️ الشروحات'],
    ['↗️ Vpn لتشغيل كامل أقسام الموقع', '↗️ ichancy apk'],
    ['💜 الشروط والأحكام'],
    ['🟣 الجاكبوت', '💵 اللفة المجانية'],
    ['🎁 البونصات والعروض الحالية'],
    ['🎰 ألعاب Ichancy', '⭐ دخول مباشر للألعاب'],
]
BACK = '🔙 رجوع للقائمة الرئيسية'
# Optional Telegram custom emoji IDs for keyboard buttons, keyed by exact button text.
# Requires a compatible Telegram Bot API / aiogram version and valid custom emoji IDs.
# Leave empty for the ordinary emoji fallback.
CUSTOM_EMOJI_IDS = {}
WELCOME_GIF = Path(__file__).with_name('welcome.gif')


def keyboard(rows):
    buttons = []
    for row in rows:
        button_row = []
        for t in row:
            emoji_id = CUSTOM_EMOJI_IDS.get(t)
            if emoji_id and 'icon_custom_emoji_id' in KeyboardButton.model_fields:
                button_row.append(KeyboardButton(text=t, icon_custom_emoji_id=emoji_id))
            else:
                button_row.append(KeyboardButton(text=t))
        buttons.append(button_row)
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, input_field_placeholder='اختر خدمة من القائمة')


def init_db():
    with sqlite3.connect(DB) as con:
        con.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, referrer_id INTEGER, joined_at TEXT DEFAULT CURRENT_TIMESTAMP)')


def save_user(user, referrer=None):
    with sqlite3.connect(DB) as con:
        con.execute('INSERT OR IGNORE INTO users (id, username, first_name, referrer_id) VALUES (?, ?, ?, ?)', (user.id, user.username, user.first_name, referrer if referrer != user.id else None))


@router.message(CommandStart())
async def start(message: Message):
    ref = None
    parts = (message.text or '').split(maxsplit=1)
    if len(parts) > 1 and parts[1].startswith('ref_'):
        try: ref = int(parts[1][4:])
        except ValueError: pass
    save_user(message.from_user, ref)
    if WELCOME_GIF.exists():
        await message.answer_animation(FSInputFile(WELCOME_GIF), caption='✨ أهلا بك في بوت Ichancy Saw', reply_markup=keyboard(ROWS))
    else:
        await message.answer('أهلا بك في بوت\nIchancy Saw', reply_markup=keyboard(ROWS))


@router.message(F.text == BACK)
async def back(message: Message):
    await message.answer('🏠 القائمة الرئيسية', reply_markup=keyboard(ROWS))


@router.message(F.text)
async def menu(message: Message, bot: Bot):
    save_user(message.from_user)
    choice = message.text
    if choice not in {item for row in ROWS for item in row}:
        await message.answer('اختار خدمة من الأزرار 👇', reply_markup=keyboard(ROWS))
        return
    if 'الإحالات' in choice:
        me = await bot.get_me()
        url = f'https://t.me/{me.username}?start=ref_{message.from_user.id}'
        with sqlite3.connect(DB) as con:
            count = con.execute('SELECT COUNT(*) FROM users WHERE referrer_id=?', (message.from_user.id,)).fetchone()[0]
        await message.answer(f'🔗 رابط إحالتك:\n{url}\n\n👥 عدد الإحالات: {count}\n\nالمكافآت المالية غير مفعلة حتى اكتمال الربط.', reply_markup=keyboard([[BACK]]))
    elif 'شحن رصيد' in choice or 'سحب رصيد' in choice:
        await message.answer('🔒 الخدمة قيد التجهيز. لا توجد عمليات مالية حقيقية قبل ربط API الرسمي والتحقق من الصلاحيات.', reply_markup=keyboard([[BACK]]))
    elif 'كود هدية' in choice or 'إهداء رصيد' in choice:
        await message.answer('🎁 نظام الهدايا قيد التجهيز، ولن يخصم أو يضيف أي رصيد حالياً.', reply_markup=keyboard([[BACK]]))
    elif 'السجل' in choice:
        await message.answer('📋 لا توجد عمليات مسجلة حالياً.', reply_markup=keyboard([[BACK]]))
    else:
        await message.answer(f'{choice}\n\n🛠️ تم تجهيز الزر. محتوى هذه الخدمة وروابطها بحاجة لإعداد من صاحب البوت.', reply_markup=keyboard([[BACK]]))


async def main():
    if not TOKEN:
        raise RuntimeError('ضع BOT_TOKEN في ملف .env أولاً')
    logging.basicConfig(level=logging.INFO)
    init_db()
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
