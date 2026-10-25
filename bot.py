import asyncio
import logging
import os
import sqlite3
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardRemove
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN', '').strip()
BOT_NAME = os.getenv('BOT_NAME', 'Sheikh').strip() or 'Sheikh'
DB = Path(__file__).with_name('users.db')
WELCOME_GIF = Path(__file__).with_name('welcome.gif')
router = Router()

ROWS = [
    [('🟥 Ichancy', 'ichancy')],
    [('💸 شحن رصيد البوت', 'deposit'), ('💰 سحب رصيد البوت', 'withdraw')],
    [('💸 نظام الإحالات', 'referrals')],
    [('🎟️ إهداء رصيد', 'gift_balance'), ('🎁 كود هدية', 'gift_code')],
    [('📝 رسالة للأدمن', 'admin_message'), ('💌 تواصل معنا', 'contact')],
    [('✅ السجل', 'history'), ('⚠️ الشروحات', 'guides')],
    [('↗️ Vpn لتشغيل كامل أقسام الموقع', 'vpn'), ('↗️ ichancy apk', 'apk')],
    [('💜 الشروط والأحكام', 'terms')],
    [('🟣 الجاكبوت', 'jackpot'), ('💵 اللفة المجانية', 'free_spin')],
    [('🎁 البونصات والعروض الحالية', 'bonuses')],
    [('🎰 ألعاب Ichancy', 'games'), ('⭐ دخول مباشر للألعاب', 'direct_games')],
]
LABELS = {key: label for row in ROWS for label, key in row}

def inline_menu(rows=ROWS):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data='menu:' + key) for label, key in row]
        for row in rows
    ])

def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🔙 رجوع للقائمة الرئيسية', callback_data='home')]
    ])

def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, referrer_id INTEGER, joined_at TEXT DEFAULT CURRENT_TIMESTAMP)')

def save_user(user, referrer=None):
    if not user:
        return
    with sqlite3.connect(DB) as conn:
        conn.execute('INSERT OR IGNORE INTO users (id, username, first_name, referrer_id) VALUES (?, ?, ?, ?)',
                     (user.id, user.username, user.first_name, referrer if referrer != user.id else None))

async def update_view(call: CallbackQuery, text: str, markup):
    # Telegram animations use captions rather than message text.
    if call.message.animation or call.message.photo or call.message.video:
        await call.message.edit_caption(caption=text, reply_markup=markup)
    else:
        await call.message.edit_text(text=text, reply_markup=markup)

@router.message(CommandStart())
async def start(message: Message):
    referrer = None
    parts = (message.text or '').split(maxsplit=1)
    if len(parts) == 2 and parts[1].startswith('ref_'):
        try:
            referrer = int(parts[1][4:])
        except ValueError:
            pass
    save_user(message.from_user, referrer)
    # Clear old reply keyboard left behind by a previous bot version.
    await message.answer('✨ أهلاً وسهلاً', reply_markup=ReplyKeyboardRemove())
    greeting = f'🏠 أهلاً بك في بوت {BOT_NAME}\nاختر الخدمة من الأزرار التالية 👇'
    if WELCOME_GIF.exists():
        await message.answer_animation(FSInputFile(WELCOME_GIF), caption=greeting, reply_markup=inline_menu())
    else:
        await message.answer(greeting, reply_markup=inline_menu())

@router.callback_query(F.data == 'home')
async def home(call: CallbackQuery):
    await update_view(call, f'🏠 القائمة الرئيسية — {BOT_NAME}\nاختر الخدمة 👇', inline_menu())
    await call.answer()

@router.callback_query(F.data.startswith('menu:'))
async def on_menu(call: CallbackQuery, bot: Bot):
    key = call.data.partition(':')[2]
    if key not in LABELS:
        await call.answer('خيار غير معروف', show_alert=True)
        return
    save_user(call.from_user)
    label = LABELS[key]
    if key == 'referrals':
        me = await bot.get_me()
        url = f'https://t.me/{me.username}?start=ref_{call.from_user.id}'
        with sqlite3.connect(DB) as conn:
            count = conn.execute('SELECT COUNT(*) FROM users WHERE referrer_id=?', (call.from_user.id,)).fetchone()[0]
        text = f'🔗 رابط إحالتك:\n{url}\n\n👥 عدد الإحالات: {count}\nالمكافآت المالية غير مفعلة.'
    elif key in ('deposit', 'withdraw'):
        text = f'{label}\n\n🔒 الخدمة قيد التجهيز. لا تُنفّذ عمليات مالية قبل تفعيل API الرسمي.'
    elif key in ('gift_balance', 'gift_code'):
        text = f'{label}\n\n🎁 الخدمة غير مفعّلة حالياً، ولا يتم تحويل أي رصيد.'
    elif key == 'history':
        text = '📋 لا توجد عمليات مسجلة في هذه النسخة التجريبية.'
    else:
        text = f'{label}\n\n🛠️ هذا القسم قيد التجهيز، ويحتاج إعداداً من صاحب البوت.'
    await update_view(call, text, back_menu())
    await call.answer()

@router.message()
async def fallback(message: Message):
    await message.answer('اكتب /start لعرض القائمة الرئيسية 👇')

async def main():
    if not TOKEN:
        raise RuntimeError('BOT_TOKEN غير موجود في متغيرات البيئة')
    logging.basicConfig(level=logging.INFO)
    init_db()
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
