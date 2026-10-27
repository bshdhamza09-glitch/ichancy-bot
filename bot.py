"""Sheikh Telegram bot. Local loyalty ledger; no Ichancy financial API calls."""
import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router, BaseMiddleware
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton, ReplyKeyboardRemove,
                           CallbackQuery, Message, BotCommand, BotCommandScopeDefault)
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN', '').strip()
NAME = os.getenv('BOT_NAME', 'Sheikh').strip() or 'Sheikh'
ADMIN_IDS = {int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip().isdigit()}
DB = Path(os.getenv('DATABASE_PATH', str(Path(__file__).with_name('sheikh.db'))))
GIF = Path(__file__).with_name('welcome.gif')
router = Router()
LOYALTY_EXCHANGES_DEFAULT = {1: 2, 6: 20, 12: 50}  # points -> local SYP bot credit
REQUIRED_CHANNEL = os.getenv('REQUIRED_CHANNEL', '@IchancyElSheikh').strip()
DEPOSIT_CHAT_ID = os.getenv('DEPOSIT_CHAT_ID', '').strip()
WITHDRAWAL_CHAT_ID = os.getenv('WITHDRAWAL_CHAT_ID', '-1004439550155').strip()
SUPPORT_CHAT_ID = os.getenv('SUPPORT_CHAT_ID', '-1004401691217').strip()
SHAM_ACCOUNT = os.getenv('SHAM_ACCOUNT', 'bbcbfd15ad74579eb0b8e9baca872e57').strip()
SYRIATEL_ACCOUNT = os.getenv('SYRIATEL_ACCOUNT', '0933185350').strip()
QR = Path(__file__).with_name('sham_qr.jpg')


TERMS_V12 = 'عند الضغط على زر موافقة فأنت توافق على الشروط القائمة ضمن البوت ويحق لك الإعتراض في حال مواجهة أي مشكلة خارجة عن شروط وقوانين البوت\n\nيرجى قراءة هذه الشّروط قبل استخدام البوت لضمان تجربة آمنة وسلسة:\n\nالبوت مخصّص لإنشاء الحسابات، والسّحب، والتعبئة الفورية لحسابات موقع Ichancy.\n\n1_منع الحسابات المتعدّدة:\nإنشاء أكثر من حساب للشّخص الواحد مخالف للقوانين، وقد يؤدّي إلى حظر الحسابات المرتبطة وتجميد أرصدتها، وذلك بناءاً على سياسة اللّعب النظيف .\n\n2_تبديل طرق الدفع غير مسموح:\nلا يُسمح بشحن رصيد وسحبه بغرض التبديل بين وسائل الدفع المختلفة. في حال اكتشاف عملية كهذه، يتم سحب الرّصيد والتّحفظ عليه دون إشعار مسبق.\n\n3_شروط أرباح الإحالات:\nتُحتسب أرباح الإحالة فقط بعد تسجيل 3 إحالات نشطة أو أكثر (أي قاموا بالتعبئة الفعلية).\n\n⛔️تنبيه:\nأي محاولة للتّحايل أو مخالفة الشروط ستؤدي إلى إيقاف الحساب وتجميد الأرصدة.'

ROWS = [
    ['🟥 Ichancy'],
    ['💸 شحن رصيد البوت', '💰 سحب رصيد البوت'],
    ['💸 نظام الإحالات'],
    ['🎟️ إهداء رصيد', '🎁 كود هدية'],
    ['📝 رسالة للأدمن', '💌 تواصل معنا'],
    ['✅ السجل', '⚠️ الشروحات'],
    ['↗️ Vpn لتشغيل كامل أقسام الموقع', '↗️ ichancy apk'],
    ['💜 الشروط والأحكام'],
    ['💵 اللفة المجانية'],
    ['🎁 البونصات والعروض الحالية'],
    ['🎰 ألعاب Ichancy', '⭐ دخول مباشر للألعاب'],
    ['🌟 نقاط الولاء'],
]
ADMIN_ROWS = [
    ['👥 المستخدمين', '🎁 العروض والبونصات'],
    ['🌟 إدارة نقاط الولاء', '📢 الإذاعة'],
    ['⚙️ إعدادات البوت', '📊 التقارير'],
    ['🎟️ الأكواد', '💰 الإحالات'],
    ['🏠 القائمة الرئيسية'],
]
USER_ADMIN_ROWS = [
    ['🔎 البحث عن مستخدم', '📜 سجل مستخدم'],
    ['➕ إضافة رصيد', '➖ خصم رصيد'],
    ['🚫 حظر مستخدم', '🔓 فك حظر مستخدم'],
    ['↩️ رجوع للوحة الأدمن'],
]
BONUS_ADMIN_ROWS = [
    ['📝 تعديل نص العروض والبونصات'],
    ['↩️ رجوع للوحة الأدمن'],
]
LOYALTY_ADMIN_ROWS = [
    ['➕ منح نقاط ولاء', '➖ خصم نقاط ولاء'],
    ['🎁 تعديل جوائز نقاط الولاء'],
    ['↩️ رجوع للوحة الأدمن'],
]
SETTINGS_ADMIN_ROWS = [
    ['⚙️ حالة البوت (تشغيل/إيقاف)'],
    ['⚙️ تعديل سعر الدولار', '🔥 حرق رقم عملية'],
    ['📝 إدارة المحتوى والروابط'],
    ['↩️ رجوع للوحة الأدمن'],
]
REPORT_ADMIN_ROWS = [['📊 تقرير'], ['↩️ رجوع للوحة الأدمن']]
CODE_ADMIN_ROWS = [
    ['🎟️ إضافة كود'],
    ['💳 تعديل أكواد شام كاش', '💳 تعديل أكواد سيريتل كاش'],
    ['↩️ رجوع للوحة الأدمن'],
]
REFERRAL_ADMIN_ROWS = [['⚙️ إعدادات نظام الإحالات'], ['📋 سجل إحالات البوت'], ['↩️ رجوع للوحة الأدمن']]
ADMIN_MENUS = {
    '👥 المستخدمين': ('👥 إدارة المستخدمين', USER_ADMIN_ROWS),
    '🎁 العروض والبونصات': ('🎁 إدارة العروض والبونصات', BONUS_ADMIN_ROWS),
    '🌟 إدارة نقاط الولاء': ('🌟 إدارة نقاط الولاء', LOYALTY_ADMIN_ROWS),
    '⚙️ إعدادات البوت': ('⚙️ إعدادات البوت', SETTINGS_ADMIN_ROWS),
    '📊 التقارير': ('📊 التقارير', REPORT_ADMIN_ROWS),
    '🎟️ الأكواد': ('🎟️ إدارة الأكواد', CODE_ADMIN_ROWS),
    '💰 الإحالات': ('💰 إدارة الإحالات', REFERRAL_ADMIN_ROWS),
}
ADMIN_ALL = {x for row in (ADMIN_ROWS + USER_ADMIN_ROWS + BONUS_ADMIN_ROWS + LOYALTY_ADMIN_ROWS + SETTINGS_ADMIN_ROWS + REPORT_ADMIN_ROWS + CODE_ADMIN_ROWS + REFERRAL_ADMIN_ROWS) for x in row}

ALL = {x for row in ROWS for x in row}

class Input(StatesGroup):
    lookup = State()
    loyalty_add = State()
    loyalty_reward = State()
    loyalty_prize_edit = State()
    loyalty_claim = State()
    award_id = State()
    ban = State()
    unban = State()
    broadcast = State()
    bonus_text = State()
    support = State()
    support_confirm = State()
    balance_change = State()
    points_change = State()
    admin_config = State()
    user_transfer = State()
    gift_redeem = State()
    admin_code = State()
    admin_code_amount = State()
    admin_code_uses = State()
    admin_search = State()
    deposit_amount = State()
    deposit_reference = State()
    deposit_sender = State()
    withdrawal_amount = State()
    withdrawal_address = State()


def db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    return con

def init():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, referrer INTEGER, points INTEGER NOT NULL DEFAULT 0, banned INTEGER NOT NULL DEFAULT 0, joined TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS bot_ledger(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, admin_id INTEGER NOT NULL, delta INTEGER NOT NULL, balance_after INTEGER NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS rewards(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, cost INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS claims(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, reward_id INTEGER NOT NULL, points_cost INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created TEXT DEFAULT CURRENT_TIMESTAMP, resolved TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, actor INTEGER, action TEXT, details TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS gift_codes(code TEXT PRIMARY KEY, amount INTEGER NOT NULL, max_uses INTEGER NOT NULL DEFAULT 1, uses INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS gift_redemptions(code TEXT NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY(code,user_id));
        CREATE TABLE IF NOT EXISTS referrals_paid(user_id INTEGER PRIMARY KEY, paid_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS referral_notifications(referred_id INTEGER PRIMARY KEY, referrer_id INTEGER NOT NULL, notified_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS referral_finance(id INTEGER PRIMARY KEY AUTOINCREMENT, referred_id INTEGER NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('deposit','withdraw')), amount INTEGER NOT NULL CHECK(amount>0), activity_day TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'admin_verified', recorded_by INTEGER NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS referral_commissions(id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER NOT NULL, referred_id INTEGER NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), status TEXT NOT NULL DEFAULT 'pending', created TEXT DEFAULT CURRENT_TIMESTAMP, paid_at TEXT);
        CREATE TABLE IF NOT EXISTS deposits(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, method TEXT NOT NULL, amount INTEGER NOT NULL, operation_id TEXT NOT NULL, sender_account TEXT, sender_name TEXT, status TEXT NOT NULL DEFAULT 'pending', requested_at TEXT DEFAULT CURRENT_TIMESTAMP, reviewed_by INTEGER, reviewed_at TEXT, UNIQUE(method,operation_id));
        CREATE TABLE IF NOT EXISTS sham_verified(user_id INTEGER PRIMARY KEY, account TEXT NOT NULL, holder TEXT NOT NULL, verified_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS loyalty_deposit_awards(deposit_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, points INTEGER NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS withdrawals(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,method TEXT NOT NULL,amount_syp INTEGER NOT NULL,fee_syp INTEGER NOT NULL,payout_syp INTEGER NOT NULL,payout_currency TEXT NOT NULL,payout_amount TEXT NOT NULL,exchange_rate INTEGER,recipient TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',requested_at TEXT DEFAULT CURRENT_TIMESTAMP,reviewed_by INTEGER,reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS support_messages(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, body TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS support_thread_map(chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY(chat_id,message_id));
        CREATE TABLE IF NOT EXISTS loyalty_exchange_options(points INTEGER PRIMARY KEY, credit INTEGER NOT NULL CHECK(credit>0), active INTEGER NOT NULL DEFAULT 1);
        
        ''')
        withdrawal_cols={r[1] for r in c.execute('PRAGMA table_info(withdrawals)')}
        for col in ('balance_before','balance_after'):
            if col not in withdrawal_cols:
                c.execute(f'ALTER TABLE withdrawals ADD COLUMN {col} INTEGER')
        cols={r[1] for r in c.execute('PRAGMA table_info(users)')}
        if 'bot_balance' not in cols: c.execute('ALTER TABLE users ADD COLUMN bot_balance INTEGER NOT NULL DEFAULT 0')
        c.execute("INSERT OR IGNORE INTO settings VALUES ('enabled','1')")
        c.execute("INSERT OR IGNORE INTO settings VALUES ('bonuses','لا توجد عروض حالية')")
        # Apply this requested default once, without overwriting later admin edits.
        if not c.execute("SELECT 1 FROM settings WHERE key='bonuses_v20_applied'").fetchone():
            c.execute("INSERT INTO settings(key,value) VALUES('bonuses','لا توجد عروض حالية') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
            c.execute("INSERT INTO settings(key,value) VALUES('bonuses_v20_applied','1')")
        for key,value in [('dollar_rate','14250'),('cashback','10'),('weekly_cashback','10'),('referral_reward','0'),('referral_percent','5'),('referral_min_active','3'),('referral_min_transfers','3'),('referral_min_days','3'),('referral_maturity_days','7'),('referral_monthly_cap','500000'),('referral_total_cap','5000000'),('terms','يرجى الالتزام بشروط استخدام البوت.'),('tutorials','لا توجد شروحات منشورة حالياً.'),('vpn_url',''),('apk_url',''),('games_url',''),('direct_url',''),('contact_url',''),('free_spin','غير متاح حالياً.'),('current_prize','لا توجد جائزة حالية.'),('sham_codes',''),('syriatel_codes','')]:
            c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(key,value))

        for points,credit in LOYALTY_EXCHANGES_DEFAULT.items():
            c.execute('INSERT OR IGNORE INTO loyalty_exchange_options(points,credit,active) VALUES(?,?,1)',(points,credit))

        # One-time terms update; later admin edits remain intact.
        if not c.execute("SELECT 1 FROM settings WHERE key='terms_v12_applied'").fetchone():
            c.execute("INSERT INTO settings(key,value) VALUES('terms',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (TERMS_V12,))
            c.execute("INSERT INTO settings(key,value) VALUES('terms_v12_applied','1')")

def audit(actor, action, details=''):
    with db() as c:
        c.execute('INSERT INTO audit(actor,action,details) VALUES(?,?,?)',(actor,action,str(details)))

def save(u, ref=None):
    with db() as c:
        valid_ref=ref if ref and ref != u.id and c.execute('SELECT 1 FROM users WHERE id=?',(ref,)).fetchone() else None
        c.execute('INSERT OR IGNORE INTO users(id,username,first_name,referrer) VALUES(?,?,?,?)', (u.id,u.username,u.first_name,valid_ref))
        c.execute('UPDATE users SET username=?,first_name=? WHERE id=?',(u.username,u.first_name,u.id))

async def notify_referrer_if_new(bot, referred_id):
    """Send once only after the referred user passes required channel membership.
    On Telegram send failure do not mark delivered, allowing a later retry.
    """
    with db() as c:
        row=c.execute('SELECT u.referrer,u.first_name,u.username FROM users u WHERE u.id=?',(referred_id,)).fetchone()
        if not row or not row['referrer']: return False
        referrer=row['referrer']
        if c.execute('SELECT 1 FROM referral_notifications WHERE referred_id=?',(referred_id,)).fetchone(): return False
        parent=c.execute('SELECT id FROM users WHERE id=?',(referrer,)).fetchone()
        if not parent: return False
        name=(row['first_name'] or 'مستخدم جديد').replace('<','').replace('>','')
        username=f"@{row['username']}" if row['username'] else 'بدون اسم مستخدم'
        count=c.execute('SELECT COUNT(*) FROM users WHERE referrer=?',(referrer,)).fetchone()[0]
    message=(f'🎉 انضم شخص جديد عن طريق رابط إحالتك!\n\n👤 الاسم: {name}\n🔖 الحساب: {username}\n🆔 المعرف: {referred_id}\n👥 إجمالي إحالاتك: {count}\n\n⏳ الإحالة قيد التفعيل حسب شروط النظام.')
    try:
        await bot.send_message(referrer,message)
    except Exception:
        logging.exception('Referral notification failed for %s -> %s',referred_id,referrer)
        return False
    with db() as c:
        c.execute('INSERT OR IGNORE INTO referral_notifications(referred_id,referrer_id) VALUES(?,?)',(referred_id,referrer))
    return True

def setting(k):
    with db() as c:
        row=c.execute('SELECT value FROM settings WHERE key=?',(k,)).fetchone()
    return row['value'] if row else ''

# Inline buttons render inside the chat message for BOTH menus.
BUTTON_IDS = {label: f'btn_{i}' for i, label in enumerate(dict.fromkeys(
    [label for group in ROWS + ADMIN_ROWS + USER_ADMIN_ROWS + BONUS_ADMIN_ROWS + LOYALTY_ADMIN_ROWS + SETTINGS_ADMIN_ROWS + REPORT_ADMIN_ROWS + CODE_ADMIN_ROWS + REFERRAL_ADMIN_ROWS for label in group] +
    ['🎁 استبدال نقاط', '➕ منح نقاط ولاء', '🎁 إنشاء جائزة ولاء', '👮 لوحة تحكم الإدارة', '↩️ رجوع للوحة الأدمن']
))}
ID_BUTTONS = {v: k for k, v in BUTTON_IDS.items()}

def keyboard(rows):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=BUTTON_IDS[label]) for label in group]
        for group in rows
    ])

def back():
    return keyboard([['🏠 القائمة الرئيسية'],['↩️ رجوع للوحة الأدمن']])

def admin(u):
    return u and u.id in ADMIN_IDS

async def joined(bot, uid):
    if uid in ADMIN_IDS: return True
    try:
        member=await bot.get_chat_member(REQUIRED_CHANNEL,uid)
        return member.status in ('creator','administrator','member') or (member.status=='restricted' and member.is_member)
    except Exception:
        logging.exception('Cannot check channel membership; ensure bot is admin in channel')
        return False

def join_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📢 اشترك بالقناة',url='https://t.me/IchancyElSheikh')],
        [InlineKeyboardButton(text='✅ تحقّق من الاشتراك',callback_data='verify_join')]])

async def require_join(bot,uid,message):
    if await joined(bot,uid): return True
    await message.answer('🔒 لازم تشترك بالقناة أولاً حتى تستخدم البوت.',reply_markup=join_keyboard())
    return False

async def deposit_menu(m):
    await m.answer('💰 اختر طريقة شحن الرصيد الداخلي (مراجعة يدوية):',reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🟢 شام كاش',callback_data='dep:sham')],
        [InlineKeyboardButton(text='📱 سيريتل كاش',callback_data='dep:syriatel')],
        [InlineKeyboardButton(text='↩️ الرئيسية',callback_data=BUTTON_IDS['🏠 القائمة الرئيسية'])]]))

async def deposit_instructions(m,method,uid):
    if method=='sham':
        rate=setting('dollar_rate')
        try:
            rate_number=float(rate)
            rate_display=f'{rate_number:g}'
        except (ValueError,TypeError):
            rate_display='14250'
        msg=(f'ارسل الى العنوان\n{SHAM_ACCOUNT}\n\n'
             '♦️ معتصم باسل شرف♦️\n\n'
             '⚠️ تحذير هام:\n'
             'لتجنب الحظر ، يرجى التقيّد باستخدام حساب شام كاش واحد فقط لكافة عمليات الشحن والسحب\n\n'
             'ثم ادخل رقم العملية\n'
             f'1 ShamCash USD = {rate_display}')
        if QR.exists():
            await m.answer_photo(FSInputFile(QR),caption='📸 رمز ShamCash للدفع')
        kb=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='📋 نسخ عنوان شام كاش',copy_text=CopyTextButton(text=SHAM_ACCOUNT))],
            [InlineKeyboardButton(text='✅ أتممت التحويل',callback_data='depgo:sham')]])
    else:
        msg=f'📱 سيريتل كاش\nحوّل إلى الرقم: {SYRIATEL_ACCOUNT}\nبالليرة السورية الجديدة فقط. بعد التحويل اضغط الزر لإرسال طلب مراجعة.'
        kb=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='📋 نسخ رقم سيريتل كاش',copy_text=CopyTextButton(text=SYRIATEL_ACCOUNT))],
            [InlineKeyboardButton(text='✅ أتممت التحويل',callback_data='depgo:syriatel')]])
    await m.answer(msg,reply_markup=kb)

async def send_deposit_to_admins(bot,deposit_id):
    with db() as c:
        r=c.execute('SELECT d.*,u.username,u.first_name FROM deposits d JOIN users u ON u.id=d.user_id WHERE d.id=?',(deposit_id,)).fetchone()
    if not r: return
    text=(f'📥 طلب إيداع #{deposit_id}\n👤 {r["first_name"]} (@{r["username"] or "بدون_يوزر"})\n🆔 {r["user_id"]}\n💳 الطريقة: {r["method"]}\n💰 المبلغ: {r["amount"]} SYP جديدة\n🔢 رقم العملية: {r["operation_id"]}\n🏦 حساب المرسل: {r["sender_account"] or "—"}\n👤 اسم صاحب الحساب: {r["sender_name"] or "—"}\n🕒 وقت الطلب UTC: {r["requested_at"]}\n⏳ بانتظار تحقق الإدارة من وصول المبلغ وهوية المرسل')
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ تأكيد الإيداع',callback_data=f'dreview:{deposit_id}:approve'),InlineKeyboardButton(text='❌ رفض',callback_data=f'dreview:{deposit_id}:reject')]])
    targets=[]
    if DEPOSIT_CHAT_ID: targets.append(DEPOSIT_CHAT_ID)
    targets.extend(aid for aid in ADMIN_IDS if aid != r['user_id'])
    sent=False
    for dest in dict.fromkeys(targets):
        try: await bot.send_message(dest,text,reply_markup=kb);sent=True
        except Exception: logging.exception('Failed to send deposit to %s',dest)
    return sent

def balance_of(uid):
    with db() as c:
        r=c.execute('SELECT bot_balance FROM users WHERE id=?',(uid,)).fetchone()
    return int(r['bot_balance']) if r else 0

def withdrawal_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🟥 سيرياتيل كاش',callback_data='wd:syriatel')],
        [InlineKeyboardButton(text='💠 شام كاش',callback_data='wd:sham_menu')],
        [InlineKeyboardButton(text='🟢 USDT',callback_data='wd:unavailable')],
        [InlineKeyboardButton(text='💸 حوالات مالية',callback_data='wd:unavailable')],
        [InlineKeyboardButton(text='🏠 القائمة الرئيسية',callback_data=BUTTON_IDS['🏠 القائمة الرئيسية'])]])

async def withdrawal_menu(m,uid):
    await m.answer(f'⬆️ سحب الرصيد\n\n💰 رصيدك الحالي: {balance_of(uid):,} ليرة سورية جديدة\n\nاختر وسيلة السحب:',reply_markup=withdrawal_keyboard())

@router.callback_query(F.data.startswith('wd:'))
async def withdrawal_choose(q:CallbackQuery,state:FSMContext):
    if not await require_join(q.bot,q.from_user.id,q.message): return await q.answer()
    await q.answer()
    method=q.data[3:]
    if method=='unavailable': return await q.message.answer('هذه الطريقة غير مفعلة حالياً، ولا يمكن تقديم طلب عبرها.')
    if method=='sham_menu':
        return await q.message.answer('💠 شام كاش\nاختر الطريقة المناسبة •••',reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='💠 شام كاش (SYP)',callback_data='wd:sham_syp')],
            [InlineKeyboardButton(text='💠 شام كاش (USD)',callback_data='wd:sham_usd')],
            [InlineKeyboardButton(text='↩️ رجوع',callback_data='wd:menu')]]))
    if method=='menu': return await withdrawal_menu(q.message,q.from_user.id)
    if method not in ('syriatel','sham_syp','sham_usd'): return
    bal=balance_of(q.from_user.id)
    if bal<=0: return await q.message.answer('❌ رصيدك الحالي صفر، لا يمكنك تقديم طلب سحب.')
    rate = None
    if method == 'sham_usd':
        try:
            from decimal import Decimal
            rate = Decimal(str(setting('dollar_rate')).strip().replace(',', ''))
            if not rate.is_finite() or rate <= 0: raise ValueError('invalid rate')
        except (ValueError, TypeError, ArithmeticError):
            return await q.message.answer('❌ سعر صرف الدولار غير مضبوط. اطلب من الأدمن تصحيحه.')
    display_balance=f'${Decimal(bal)/rate:,.2f}' if method=='sham_usd' else f'{bal:,} ليرة سورية جديدة'
    title={'syriatel':'🟥 سيرياتيل كاش','sham_syp':'💠 شام كاش (SYP)','sham_usd':'💠 شام كاش (USD)'}[method]
    currency='USD' if method=='sham_usd' else 'SYP'
    bounds='⬇️ الحد الأدنى للسحب: 400\n⬆️ الحد الأقصى للسحب: 50000\n\n' if method=='syriatel' else ''
    await state.set_state(Input.withdrawal_amount)
    await state.update_data(withdrawal_method=method)
    await q.message.answer(f'{title}\n\n💱 العملة: {currency}\n\n{bounds}🏷 رسوم السحب: 10%\n\n💰 رصيدك الحالي: {display_balance}\n\nادخل المبلغ الذي تريد سحبه ⏳'+('\n(المبلغ بالدولار، وسعر الصرف المعتمد: '+str(rate)+' SYP لكل USD)' if method=='sham_usd' else ''))

@router.message(Command('cancel'))
@router.message(F.text.in_({'/الغاء العملية الحالية', '/إلغاء العملية الحالية', 'إلغاء العملية الحالية'}))
async def quick_cancel(m: Message, state: FSMContext):
    current = await state.get_state()
    await state.clear()
    await m.answer('✅ تم إلغاء العملية الحالية.' if current else 'ℹ️ ما في عملية جارية حالياً.​')

@router.message(Command('balance'))
@router.message(F.text.in_({'/رصيدي', 'رصيدي'}))
async def quick_balance(m: Message):
    save(m.from_user)
    with db() as c:
        r = c.execute('SELECT bot_balance,points FROM users WHERE id=?', (m.from_user.id,)).fetchone()
    await m.answer(f'💰 رصيدك داخل بوت Sheikh: {r["bot_balance"]:,}\n🌟 نقاط الولاء: {r["points"]:,}\n\nرصيد Ichancy منفصل وغير مربوط حالياً.')


@router.message(CommandStart())
async def start(m: Message, state:FSMContext):
    await state.clear()
    ref=None
    p=(m.text or '').split(maxsplit=1)
    if len(p)>1 and p[1].startswith('ref_'):
        try: ref=int(p[1][4:])
        except ValueError: pass
    save(m.from_user,ref)
    if not await require_join(m.bot,m.from_user.id,m): return
    await notify_referrer_if_new(m.bot,m.from_user.id)
    await home(m,True)

@router.message(Command('admin'))
@router.message(F.text == '👮 لوحة تحكم الإدارة')
async def panel(m:Message,state:FSMContext):
    if not admin(m.from_user): return await m.answer('غير مصرح لك بالدخول.')
    await state.clear()
    await m.answer('👮 لوحة تحكم الإدارة — Sheikh',reply_markup=keyboard(ADMIN_ROWS))

@router.message(F.text == '🏠 القائمة الرئيسية')
async def go_home(m:Message,state:FSMContext):
    await state.clear()
    await home(m)

def loyalty_options():
    with db() as c:
        return c.execute('SELECT points,credit FROM loyalty_exchange_options WHERE active=1 ORDER BY points').fetchall()

def loyalty_exchange_keyboard():
    rows=[[InlineKeyboardButton(text=f'💎 {r["points"]} نقطة',callback_data=f'loyalty:{r["points"]}')] for r in loyalty_options()]
    rows.append([InlineKeyboardButton(text='💝 عودة',callback_data=BUTTON_IDS['🏠 القائمة الرئيسية'])])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Input.withdrawal_amount, F.text, ~F.text.startswith("/"))
async def withdrawal_amount(m:Message,state:FSMContext):
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    import unicodedata
    data = await state.get_data()
    method = data.get('withdrawal_method')
    if method not in ('syriatel', 'sham_syp', 'sham_usd'):
        await state.clear()
        return await m.answer('انتهت عملية السحب. افتح قائمة السحب واختر الطريقة من جديد.')
    raw = (m.text or '').strip()
    # Convert Arabic/Persian digits, accept ordinary positive amounts without extra restrictions.
    normalized = ''.join(str(unicodedata.decimal(ch)) if ch.isdecimal() else ch for ch in raw)
    normalized = normalized.replace('٬', '').replace(',', '').replace('٫', '.')
    try:
        if not normalized or normalized.count('.') > 1 or any(ch not in '0123456789.' for ch in normalized):
            raise ValueError('not numeric')
        amount = Decimal(normalized)
        if not amount.is_finite() or amount <= 0:
            raise ValueError('invalid amount')
        rate = None
        if method == 'sham_usd':
            try:
                rate = Decimal(str(setting('dollar_rate')).strip().replace(',', ''))
                if not rate.is_finite() or rate <= 0: raise ValueError('invalid rate')
            except (ValueError, TypeError, ArithmeticError):
                return await m.answer('❌ سعر صرف الدولار غير مضبوط. اطلب من الأدمن تصحيحه.')
            syp = int((amount * rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        else:
            if amount != amount.to_integral_value():
                return await m.answer('❌ اكتب المبلغ بالليرة بدون كسور، مثل 2000.')
            syp = int(amount)
    except (ValueError, InvalidOperation, TypeError, ArithmeticError, OverflowError) as exc:
        logging.warning('Withdrawal invalid numeric input user=%s text=%r: %s', m.from_user.id, raw, exc)
        return await m.answer('❌ اكتب مبلغ السحب بالأرقام فقط، مثل 2000.')
    if syp <= 0:
        return await m.answer('❌ اكتب مبلغ سحب أكبر من صفر.')
    if method=='syriatel' and not (400<=syp<=50000): return await m.answer('❌ المبلغ لازم يكون بين 400 و50000 ليرة سورية جديدة.')
    if syp>balance_of(m.from_user.id): return await m.answer('❌ رصيدك غير كافٍ. لا يمكنك سحب أكثر من رصيدك الداخلي.')
    fee=(syp*10+99)//100
    payout=syp-fee
    if payout<=0: return await m.answer('❌ المبلغ أقل من رسوم السحب.')
    out=f'{Decimal(payout)/rate:.2f}' if method=='sham_usd' else str(payout)
    await state.update_data(withdrawal_syp=syp,withdrawal_fee=fee,withdrawal_payout=payout,withdrawal_out=out,withdrawal_rate=rate)
    await state.set_state(Input.withdrawal_address)
    if method=='syriatel': return await m.answer('📱 أرسل رقم السيرياتيل الذي ترغب في استقبال أرباحك عليه:')
    with db() as c: bound=c.execute('SELECT account FROM sham_verified WHERE user_id=?',(m.from_user.id,)).fetchone()
    if bound:
        await m.answer(f'🏦 عنوان شام كاش المعتمد لإيداعاتك السابقة:\n<code>{bound["account"]}</code>\n\nأرسل نفس العنوان لتأكيد طلب السحب. لا يمكن تغييره إلا بعد مراجعة الإدارة.',parse_mode='HTML')
    else:
        await m.answer('🏦 أرسل عنوان شام كاش للسحب.\n⚠️ لا يوجد عنوان مرسل معتمد محفوظ بعد؛ ستراجع الإدارة العنوان يدوياً قبل التحويل.')

@router.message(Input.withdrawal_address, F.text, ~F.text.startswith("/"))
async def withdrawal_address(m:Message,state:FSMContext):
    recipient=(m.text or '').strip()
    data=await state.get_data()
    method=data['withdrawal_method']
    if not (4<=len(recipient)<=150) or '\n' in recipient: return await m.answer('أرسل عنواناً أو رقماً صحيحاً في سطر واحد.')
    if method=='syriatel' and (not recipient.isdigit() or len(recipient)!=10 or not recipient.startswith('09')):
        return await m.answer('أرسل رقم سيريتل سوري صحيحاً من 10 خانات يبدأ بـ 09.')
    if method.startswith('sham'):
        with db() as c: bound=c.execute('SELECT account FROM sham_verified WHERE user_id=?',(m.from_user.id,)).fetchone()
        if bound and recipient!=bound['account']: return await m.answer('❌ يجب استخدام عنوان شام كاش المعتمد من إيداعك السابق. راجع الإدارة لتغييره.')
    await state.clear()
    try:
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            # Reserve funds atomically to prevent duplicate withdrawal requests.
            c.execute('INSERT OR IGNORE INTO users(id) VALUES(?)',(m.from_user.id,))
            before=c.execute('SELECT bot_balance FROM users WHERE id=?',(m.from_user.id,)).fetchone()['bot_balance']
            new=add_local_balance(c,m.from_user.id,-data['withdrawal_syp'],m.from_user.id)
            cur=c.execute('INSERT INTO withdrawals(user_id,method,amount_syp,fee_syp,payout_syp,payout_currency,payout_amount,exchange_rate,recipient,balance_before,balance_after) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(
                m.from_user.id,method,data['withdrawal_syp'],data['withdrawal_fee'],data['withdrawal_payout'],'USD' if method=='sham_usd' else 'SYP',data['withdrawal_out'],data['withdrawal_rate'] if method=='sham_usd' else None,recipient,before,new))
            wid=cur.lastrowid
    except ValueError: return await m.answer('❌ الرصيد غير كافٍ أو تغيّر أثناء الطلب. لم يتم تقديم السحب.')
    await m.answer(f'⏳ تم تسجيل طلب السحب #{wid}، وحجز {data["withdrawal_syp"]:,} ليرة جديدة من رصيدك.\nصافي المستحق: {data["withdrawal_out"]} {"USD" if method=="sham_usd" else "SYP"}\nالرصيد المتبقي: {new:,} SYP\nبانتظار مراجعة الإدارة والتحويل اليدوي.')
    await send_withdrawal_admin(m.bot,wid)

async def send_withdrawal_admin(bot,wid):
    with db() as c: r=c.execute('SELECT * FROM withdrawals WHERE id=?',(wid,)).fetchone()
    if not r: return
    msg=f'📤 طلب سحب #{wid}\n🆔 المستخدم: {r["user_id"]}\n💳 الطريقة: {r["method"]}\n💰 الرصيد قبل الطلب: {r["balance_before"]:,} SYP\n💰 المبلغ المحجوز: {r["amount_syp"]:,} SYP جديدة\n💰 الرصيد بعد الحجز: {r["balance_after"]:,} SYP\n🏷 الرسوم: {r["fee_syp"]:,} SYP\n💸 الصافي: {r["payout_amount"]} {r["payout_currency"]}\n🏦 الوجهة: {r["recipient"]}\n⏳ لا توافق إلا بعد إرسال المبلغ فعلياً.'
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ تم التحويل — موافقة',callback_data=f'wreview:{wid}:approve'),InlineKeyboardButton(text='❌ رفض وإعادة الرصيد',callback_data=f'wreview:{wid}:reject')]])
    targets=([WITHDRAWAL_CHAT_ID] if WITHDRAWAL_CHAT_ID else [])+list(ADMIN_IDS)
    sent=False
    for dest in dict.fromkeys(targets):
        try: await bot.send_message(dest,msg,reply_markup=kb);sent=True
        except Exception: logging.exception('Withdrawal notification failed to %s',dest)
    return sent

@router.callback_query(F.data.startswith('wreview:'))
async def review_withdrawal(q:CallbackQuery):
    if not admin(q.from_user): return await q.answer('غير مصرح',show_alert=True)
    try: _,wid,action=q.data.split(':'); wid=int(wid)
    except (ValueError,AttributeError): return await q.answer('طلب غير صحيح',show_alert=True)
    if action not in ('approve','reject'): return await q.answer('إجراء غير صحيح',show_alert=True)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        r=c.execute('SELECT * FROM withdrawals WHERE id=?',(wid,)).fetchone()
        if not r or r['status']!='pending': return await q.answer('الطلب عولج مسبقاً',show_alert=True)
        c.execute('UPDATE withdrawals SET status=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?',('approved' if action=='approve' else 'rejected',q.from_user.id,wid))
        if action=='reject': add_local_balance(c,r['user_id'],r['amount_syp'],q.from_user.id)
    await q.answer('تمت معالجة الطلب')
    try: await q.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    note=(f'✅ تمت الموافقة على طلب السحب #{wid}. ستصلك أرباحك بعد قليل.' if action=='approve' else f'❌ تم رفض طلب السحب #{wid} وإعادة كامل المبلغ المحجوز إلى رصيدك الداخلي.')
    try: await q.bot.send_message(r['user_id'],note)
    except Exception: logging.exception('Withdrawal notification to user failed')
    await q.message.answer(f'طلب السحب #{wid}: {action} بواسطة {q.from_user.id}')

@router.callback_query(F.data=='verify_join')
async def verify_join(q:CallbackQuery):
    if await joined(q.bot,q.from_user.id):
        await q.answer('تم التحقق',show_alert=True)
        save(q.from_user)
        await notify_referrer_if_new(q.bot,q.from_user.id)
        await home(q.message)
    else: await q.answer('ما قدرنا نتحقق من الاشتراك. تأكد إنك مشترك وإن البوت أدمن بالقناة.',show_alert=True)

@router.callback_query(F.data.startswith('dep:'))
async def select_deposit(q:CallbackQuery):
    await q.answer()
    if not await require_join(q.bot,q.from_user.id,q.message): return
    await deposit_instructions(q.message,q.data.split(':')[1],q.from_user.id)

@router.callback_query(F.data.startswith('depgo:'))
async def begin_deposit(q:CallbackQuery,state:FSMContext):
    await q.answer()
    if not await require_join(q.bot,q.from_user.id,q.message): return
    method=q.data.split(':')[1]
    await state.set_state(Input.deposit_amount)
    await state.update_data(deposit_method=method)
    await q.message.answer('💰 اكتب المبلغ المحوّل بالليرة السورية الجديدة (رقم صحيح موجب):')

@router.message(Input.deposit_amount)
async def deposit_amount(m:Message,state:FSMContext):
    try:
        amount=int((m.text or '').strip())
        if amount<=0 or amount>1000000000: raise ValueError()
    except ValueError: return await m.answer('اكتب مبلغ صحيح موجب.')
    await state.update_data(deposit_amount=amount)
    await state.set_state(Input.deposit_reference)
    await m.answer('🔢 أرسل رقم عملية التحويل الموجود في إيصال الدفع:')

@router.message(Input.deposit_reference)
async def deposit_reference(m:Message,state:FSMContext):
    ref=(m.text or '').strip()
    if not 3<=len(ref)<=100: return await m.answer('أرسل رقم عملية صحيح (3 إلى 100 حرف).')
    await state.update_data(deposit_reference=ref)
    data=await state.get_data()
    if data['deposit_method']=='sham':
        await state.set_state(Input.deposit_sender)
        await m.answer('🏦 أرسل كود حساب شام كاش الذي حولت منه، ثم فاصلة | ثم الاسم الظاهر لصاحب الحساب. مثال: account123 | أحمد محمد\n⚠️ هذه البيانات تصريح منك، وستتحقق الإدارة منها في إيصال التحويل.')
    else: await finish_deposit(m,state)

@router.message(Input.deposit_sender)
async def deposit_sender(m:Message,state:FSMContext):
    parts=(m.text or '').split('|',1)
    if len(parts)!=2 or not all(p.strip() for p in parts): return await m.answer('أرسل: كود حسابك | اسم صاحب الحساب')
    if len(parts[0].strip())>150 or len(parts[1].strip())>150: return await m.answer('البيانات طويلة جداً.')
    await state.update_data(sender_account=parts[0].strip(),sender_name=parts[1].strip())
    await finish_deposit(m,state)

async def finish_deposit(m,state):
    data=await state.get_data()
    await state.clear()
    if not await require_join(m.bot,m.from_user.id,m): return
    save(m.from_user)
    try:
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            bound=c.execute('SELECT account FROM sham_verified WHERE user_id=?',(m.from_user.id,)).fetchone()
            if data['deposit_method']=='sham' and bound and bound['account']!=data.get('sender_account'):
                raise ValueError('حساب شام كاش مختلف عن الحساب المعتمد. تواصل مع الإدارة لمراجعة الحالة؛ لم يُنشأ طلب تلقائي.')
            cur=c.execute('INSERT INTO deposits(user_id,method,amount,operation_id,sender_account,sender_name) VALUES(?,?,?,?,?,?)',
                          (m.from_user.id,data['deposit_method'],data['deposit_amount'],data['deposit_reference'],data.get('sender_account'),data.get('sender_name')))
            did=cur.lastrowid
    except sqlite3.IntegrityError: return await m.answer('⚠️ رقم العملية مستخدم مسبقاً لهذه الطريقة. تواصل مع الإدارة.')
    except ValueError as e: return await m.answer(str(e))
    sent=await send_deposit_to_admins(m.bot,did)
    await m.answer(f'📥 تم تسجيل طلبك رقم #{did} للمراجعة اليدوية. لن يُضاف الرصيد إلا بعد تحقق الإدارة من التحويل.' + ('' if sent else '\n⚠️ تعذر إرسال إشعار الإدارة، تواصل مع الدعم.'))

@router.callback_query(F.data.startswith('dreview:'))
async def review_deposit(q:CallbackQuery):
    if not admin(q.from_user): return await q.answer('غير مصرح',show_alert=True)
    _,sid,action=q.data.split(':')
    did=int(sid)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        r=c.execute('SELECT * FROM deposits WHERE id=?',(did,)).fetchone()
        if not r or r['status']!='pending': return await q.answer('الطلب تمت معالجته مسبقاً',show_alert=True)
        if action=='approve' and r['method']=='sham':
            bound=c.execute('SELECT account FROM sham_verified WHERE user_id=?',(r['user_id'],)).fetchone()
            if bound and bound['account']!=r['sender_account']: return await q.answer('حساب شام كاش مختلف! رفض التفعيل.',show_alert=True)
            if not r['sender_account'] or not r['sender_name']: return await q.answer('هوية المرسل ناقصة',show_alert=True)
        status='approved' if action=='approve' else 'rejected'
        c.execute('UPDATE deposits SET status=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?',(status,q.from_user.id,did))
        if action=='approve':
            new=add_local_balance(c,r['user_id'],r['amount'],q.from_user.id)
            earned_points = r['amount'] // 200
            if earned_points > 0:
                award = c.execute('INSERT OR IGNORE INTO loyalty_deposit_awards(deposit_id,user_id,points) VALUES(?,?,?)', (did,r['user_id'],earned_points))
                if award.rowcount:
                    c.execute('UPDATE users SET points=points+? WHERE id=?', (earned_points,r['user_id']))
            if r['method']=='sham': c.execute('INSERT OR IGNORE INTO sham_verified(user_id,account,holder) VALUES(?,?,?)',(r['user_id'],r['sender_account'],r['sender_name']))
    await q.answer('تمت معالجة الطلب')
    try: await q.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    try: await q.bot.send_message(r['user_id'],f'{"✅ تمت الموافقة على" if action=="approve" else "❌ تم رفض"} طلب الإيداع #{did}.' + (f'\nرصيدك الداخلي الآن: {new}\n🌟 نقاط الولاء المكتسبة: {earned_points} (نقطة لكل 200 SYP جديدة)' if action=='approve' else ''))
    except Exception: pass
    await q.message.answer(f'الطلب #{did}: {status} بواسطة {q.from_user.id}.')

async def home(m, welcome=False):
    msg=f'🏠 أهلاً بك في بوت {NAME}\nاختر الخدمة من القائمة التالية 👇'
    if welcome and GIF.exists() and os.getenv('SEND_WELCOME_GIF','0')=='1':
        await m.answer_animation(FSInputFile(GIF), caption=msg)
    else:
        await m.answer(msg, reply_markup=keyboard(ROWS))
    if welcome and GIF.exists() and os.getenv('SEND_WELCOME_GIF','0')=='1':
        await m.answer('📋 القائمة الرئيسية',reply_markup=keyboard(ROWS))

@router.callback_query(F.data.startswith(('btn_', 'ul:', 'ud:', 'ua:', 'uc:', 'ac:', 'gift:', 'loyalty:')))
async def click_button(q: CallbackQuery, state: FSMContext, bot: Bot):
    if not admin(q.from_user) and not await require_join(bot,q.from_user.id,q.message):
        await q.answer()
        return
    if q.data.startswith(('ul:', 'ud:', 'ua:', 'uc:')):
        if not admin(q.from_user): return await q.answer('غير مصرح', show_alert=True)
        await q.answer()
        return await user_callback(q, state)
    if q.data.startswith('ac:'):
        if not admin(q.from_user): return await q.answer('غير مصرح',show_alert=True)
        await q.answer()
        return await admin_action(q.message.model_copy(update={'from_user':q.from_user}),state,q.from_user,q.data[3:])
    if q.data.startswith('loyalty:'):
        return await loyalty_exchange(q)
    if q.data.startswith('gift:'):
        await q.answer()
        return await redeem_code(q.from_user.id,q.data[5:],q.message)
    label = ID_BUTTONS.get(q.data)
    if not label or not q.message:
        return await q.answer('زر غير معروف', show_alert=True)
    await q.answer()
    # Callback messages are sent by the bot; substitute the actual clicking user.
    m = q.message.model_copy(update={'from_user': q.from_user, 'text': label})
    if label == '↩️ رجوع للوحة الأدمن':
        if not admin(q.from_user): return await q.answer('غير مصرح', show_alert=True)
        await state.clear()
        return await q.message.edit_text('👮 لوحة تحكم الإدارة — Sheikh', reply_markup=keyboard(ADMIN_ROWS))
    if label == '👥 المستخدمين':
        if not admin(q.from_user): return await q.answer('غير مصرح', show_alert=True)
        return await show_user_list(q.message, 0)
    if label in ADMIN_MENUS and label != '🌟 نقاط الولاء':
        if not admin(q.from_user): return await q.answer('غير مصرح', show_alert=True)
        title, rows=ADMIN_MENUS[label]
        return await q.message.edit_text(title, reply_markup=keyboard(rows))
    if label == '🏠 القائمة الرئيسية':
        return await go_home(m, state)
    if label == '👮 لوحة تحكم الإدارة':
        return await panel(m, state)
    routes = {
        '🌟 نقاط الولاء': lambda: loyalty(m),
        '🎁 استبدال نقاط': lambda: claim_start(m, state),

        '➕ منح نقاط ولاء': lambda: add_start(m, state),
        '➖ خصم نقاط ولاء': lambda: subtract_points_start(m, state),
        '🎁 تعديل جوائز نقاط الولاء': lambda: loyalty_prizes_admin(m, state),
        '⚡ تعجيل جوائز نقاط الولاء': lambda: awards(m, state),
        '👥 المستخدمين': lambda: users(m),
        '📊 تقرير': lambda: report(m),
        '🔎 البحث عن مستخدم': lambda: lookup_start(m, state),
        '🚫 حظر مستخدم': lambda: ban_start(m, state),
        '🔓 فك حظر مستخدم': lambda: ban_start(m, state),
        '⚙️ حالة البوت (تشغيل/إيقاف)': lambda: toggle(m),
        '📝 تعديل نص البونصات والعروض الحالية': lambda: bonus_start(m, state),
        '📢 الإذاعة': lambda: broadcast_start(m, state),
        '📝 رسالة للأدمن': lambda: support_start(m, state),
        '🎟️ إهداء رصيد': lambda: transfer_start(m,state),
        '🎁 كود هدية': lambda: gift_start(m,state),
        '🔎 البحث عن مستخدم': lambda: admin_search_start(m,state),
    }
    if label in ADMIN_ALL and not admin(q.from_user):
        return await q.answer('غير مصرح لك بالدخول', show_alert=True)
    if label in routes:
        return await routes[label]()
    if label in ADMIN_ALL:
        return await admin_action(q.message.model_copy(update={'from_user':q.from_user}),state,q.from_user,label)
    if label=='💸 نظام الإحالات': return await referral_screen(q.message,bot,q.from_user.id)
    if label=='💸 شحن رصيد البوت': return await deposit_menu(q.message)
    if label=='💰 سحب رصيد البوت': return await withdrawal_menu(q.message,q.from_user.id)
    if label=='🟥 Ichancy': return await q.message.answer('خدمة Ichancy قيد الربط بالـ API الرسمي.')
    if label in ALL:
        return await services(m, bot)

@router.message(F.text == '🌟 نقاط الولاء')
async def loyalty(m:Message):
    save(m.from_user)
    with db() as c:
        u=c.execute('SELECT points,bot_balance FROM users WHERE id=?',(m.from_user.id,)).fetchone()
    offers=loyalty_options()
    menu='\n'.join(f'💎 {r["points"]} نقطة ⏪ 💰 {r["credit"]:,} ليرة سورية رصيد' for r in offers) or 'لا توجد جوائز متاحة حالياً.'
    await m.answer('🎊 قائمة استبدال الجواهر بالرصيد:\n\n'+menu+'\n\nاضغط على الخيار المناسب لك من الأسفل للاستبدال الفوري\n\n'+f'🌟 نقاطك المتاحة: {u["points"]:,}\n💰 رصيد البوت الداخلي: {u["bot_balance"]:,} ل.س',reply_markup=loyalty_exchange_keyboard())

async def loyalty_exchange(q:CallbackQuery):
    try:
        cost=int(q.data.split(':',1)[1])
    except (ValueError,IndexError):
        return await q.answer('خيار غير صالح',show_alert=True)
    # Prize must be read from DB, not a hardcoded menu.
    with db() as c:
        option=c.execute('SELECT credit FROM loyalty_exchange_options WHERE points=? AND active=1',(cost,)).fetchone()
    if not option:
        return await q.answer('الجائزة غير متاحة حالياً',show_alert=True)
    credit=option['credit']
    # A single IMMEDIATE transaction protects points and credit against concurrent clicks.
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        # Recheck the option under the same write transaction to avoid stale prize values.
        option=c.execute('SELECT credit FROM loyalty_exchange_options WHERE points=? AND active=1',(cost,)).fetchone()
        if not option:
            c.rollback()
            return await q.answer('الجائزة تغيّرت، افتح القائمة مجدداً',show_alert=True)
        credit=option['credit']
        changed=c.execute('UPDATE users SET points=points-? WHERE id=? AND points>=?',
                          (cost,q.from_user.id,cost)).rowcount
        if not changed:
            c.rollback()
            return await q.answer('❌ نقاط الولاء غير كافية',show_alert=True)
        balance=add_local_balance(c,q.from_user.id,credit,0)
        points=c.execute('SELECT points FROM users WHERE id=?',(q.from_user.id,)).fetchone()['points']
        c.execute('INSERT INTO audit(actor,action,details) VALUES(?,?,?)',
                  (q.from_user.id,'loyalty_auto_exchange',f'{cost} points -> {credit} local SYP'))
    await q.answer('تم الاستبدال بنجاح ✅',show_alert=True)
    await q.message.answer(
        f'✅ تم استبدال {cost} نقطة ولاء مقابل {credit} ليرة سورية رصيد داخل البوت.\n'
        f'🌟 نقاطك المتبقية: {points}\n💰 رصيدك الداخلي: {balance} ل.س\n'
        'ملاحظة: الرصيد داخلي ولا يتم تحويله إلى Ichancy.',
        reply_markup=loyalty_exchange_keyboard())

@router.message(F.text == '🎁 استبدال نقاط')
async def claim_start(m:Message,state:FSMContext):
    await state.set_state(Input.loyalty_claim)
    await m.answer('ابعث رقم الجائزة (مثلاً 1). النقاط تُحجز عند الطلب ولا تُصرف جائزة تلقائياً.',reply_markup=back())

@router.message(Input.loyalty_claim)
async def claim_finish(m:Message,state:FSMContext):
    if not (m.text or '').isdigit(): return await m.answer('أرسل رقم الجائزة فقط.')
    rid=int(m.text)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        reward=c.execute('SELECT * FROM rewards WHERE id=? AND active=1',(rid,)).fetchone()
        user=c.execute('SELECT points FROM users WHERE id=?',(m.from_user.id,)).fetchone()
        if not reward or not user or user['points']<reward['cost']:
            return await m.answer('الجائزة غير موجودة أو نقاطك غير كافية.')
        c.execute('UPDATE users SET points=points-? WHERE id=?',(reward['cost'],m.from_user.id))
        cur=c.execute('INSERT INTO claims(user_id,reward_id,points_cost) VALUES(?,?,?)',(m.from_user.id,rid,reward['cost']))
        cid=cur.lastrowid
    audit(m.from_user.id,'claim_created',cid)
    await state.clear()
    await m.answer(f'تم تسجيل طلب الجائزة #{cid} وهو بانتظار مراجعة الأدمن.',reply_markup=keyboard(ROWS))
    for aid in ADMIN_IDS:
        try: await m.bot.send_message(aid,f'🎁 طلب جائزة ولاء جديد #{cid}\nالمستخدم: {m.from_user.id}\nاستخدم زر ⚡ تعجيل جوائز نقاط الولاء')
        except Exception: logging.exception('Could not notify admin')

@router.message(F.text == '🌟 إدارة نقاط الولاء')
async def loyalty_admin(m:Message):
    if not admin(m.from_user): return
    with db() as c:
        pending=c.execute("SELECT COUNT(*) n FROM claims WHERE status='pending'").fetchone()['n']
        rewards=c.execute('SELECT id,title,cost,active FROM rewards ORDER BY id DESC LIMIT 12').fetchall()
    txt='\n'.join(f"#{r['id']} {r['title']} — {r['cost']} نقطة {'🟢' if r['active'] else '🔴'}" for r in rewards) or 'لا توجد جوائز'
    await m.answer('🌟 إدارة نقاط الولاء\nيمكنك منح نقاط أو تعديل جوائز الاستبدال الفوري.',reply_markup=keyboard(LOYALTY_ADMIN_ROWS))

@router.message(F.text == '➕ منح نقاط ولاء')
async def add_start(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    await state.set_state(Input.loyalty_add)
    await m.answer('ابعث: Telegram_ID عدد_النقاط\nمثال: 123456789 50',reply_markup=back())

@router.message(Input.loyalty_add)
async def add_finish(m:Message,state:FSMContext):
    try:
        uid,pts=map(int,(m.text or '').split())
        assert 0<pts<=1000000
    except (ValueError,AssertionError): return await m.answer('الصيغة غير صحيحة. مثال: 123456789 50')
    with db() as c:
        cur=c.execute('UPDATE users SET points=points+? WHERE id=?',(pts,uid))
        found=cur.rowcount
    if not found: return await m.answer('المستخدم غير موجود، لازم يبدأ البوت أولاً.')
    audit(m.from_user.id,'loyalty_points_added',f'{uid}:{pts}')
    await notify_user(m.bot,uid,f'🌟 أضافت الإدارة {pts} نقطة ولاء لحسابك.')
    await state.clear()
    await m.answer(f'تمت إضافة {pts} نقطة للمستخدم {uid}.',reply_markup=keyboard(LOYALTY_ADMIN_ROWS))

@router.message(F.text == '➖ خصم نقاط ولاء')
async def subtract_points_start(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    await state.set_state(Input.points_change)
    await state.update_data(loyalty_direct_debit=True)
    await m.answer('➖ خصم نقاط ولاء\nأرسل: Telegram_ID عدد_النقاط\nمثال: 123456789 5\nلن يتم خصم أكثر من رصيد نقاط المستخدم.')

@router.message(Input.points_change, F.text.regexp(r'^\s*\d+\s+\d+\s*$'))
async def subtract_points_finish(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    data=await state.get_data()
    if not data.get('loyalty_direct_debit'): return
    uid,pts=map(int,m.text.split())
    if not 0<pts<=9223372036854775807:
        return await m.answer('❌ عدد النقاط غير صالح.')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT points FROM users WHERE id=?',(uid,)).fetchone()
        if not row: return await m.answer('❌ المستخدم غير موجود.')
        if row['points']<pts: return await m.answer(f'❌ نقاط المستخدم {row["points"]} فقط.')
        new=row['points']-pts
        c.execute('UPDATE users SET points=? WHERE id=?',(new,uid))
        c.execute('INSERT INTO audit(actor,action,details) VALUES(?,?,?)',(m.from_user.id,'loyalty_points_deducted',f'{uid}:{pts}'))
    await state.clear()
    await notify_user(m.bot,uid,f'➖ خصمت الإدارة {pts} نقطة ولاء.\n🌟 نقاطك الحالية: {new}')
    await m.answer(f'✅ تم خصم {pts} نقطة من {uid}. المتبقي: {new}',reply_markup=keyboard(LOYALTY_ADMIN_ROWS))

@router.message(F.text == '🎁 تعديل جوائز نقاط الولاء')
async def loyalty_prizes_admin(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    await state.set_state(Input.loyalty_prize_edit)
    offers=loyalty_options()
    listing='\n'.join(f'💎 {r["points"]} نقطة = {r["credit"]} ل.س' for r in offers)
    await m.answer('🎁 تعديل جوائز الولاء\n'+listing+'\n\nلإضافة أو تعديل جائزة أرسل: عدد_النقاط قيمة_الرصيد\nمثال: 6 20\nلحذف جائزة أرسل: حذف 6\nللخروج اكتب /cancel',reply_markup=back())

@router.message(Input.loyalty_prize_edit)
async def loyalty_prizes_edit(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    parts=(m.text or '').strip().split()
    try:
        if len(parts)==2 and parts[0]=='حذف':
            points=int(parts[1]); assert points>0
            with db() as c:
                c.execute('BEGIN IMMEDIATE')
                n=c.execute('UPDATE loyalty_exchange_options SET active=0 WHERE points=? AND active=1',(points,)).rowcount
            if not n: return await m.answer('الجائزة غير موجودة.')
            audit(m.from_user.id,'loyalty_prize_disabled',str(points))
            return await m.answer(f'✅ تم إخفاء جائزة {points} نقطة. أرسل تعديلاً آخر أو /cancel.')
        if len(parts)!=2: raise ValueError()
        points,credit=map(int,parts)
        if not (1<=points<=1000000 and 1<=credit<=100000000): raise ValueError()
    except (ValueError,AssertionError):
        return await m.answer('صيغة غير صحيحة. مثال: 12 50 أو حذف 12')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('INSERT INTO loyalty_exchange_options(points,credit,active) VALUES(?,?,1) ON CONFLICT(points) DO UPDATE SET credit=excluded.credit,active=1',(points,credit))
    audit(m.from_user.id,'loyalty_prize_changed',f'{points}:{credit}')
    await m.answer(f'✅ تم حفظ الجائزة: {points} نقطة مقابل {credit} ل.س\nأرسل تعديلاً آخر أو /cancel.')

@router.message(F.text == '🎁 إنشاء جائزة ولاء')
async def reward_start(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    await state.set_state(Input.loyalty_reward)
    await m.answer('ابعث اسم الجائزة | عدد النقاط\nمثال: هدية رمزية | 100',reply_markup=back())

@router.message(Input.loyalty_reward)
async def reward_finish(m:Message,state:FSMContext):
    try:
        title,cost=(x.strip() for x in (m.text or '').split('|',1))
        cost=int(cost)
        assert title and 0<cost<=100000000
    except (ValueError,AssertionError): return await m.answer('الصيغة غير صحيحة. مثال: هدية رمزية | 100')
    with db() as c:
        rid=c.execute('INSERT INTO rewards(title,cost) VALUES(?,?)',(title,cost)).lastrowid
    audit(m.from_user.id,'reward_created',rid)
    await state.clear()
    await m.answer(f'تم إنشاء الجائزة #{rid}: {title} مقابل {cost} نقطة.',reply_markup=keyboard(LOYALTY_ADMIN_ROWS))

@router.message(F.text == '⚡ تعجيل جوائز نقاط الولاء')
async def awards(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    with db() as c:
        rows=c.execute("SELECT c.id,c.user_id,c.points_cost,r.title FROM claims c JOIN rewards r ON r.id=c.reward_id WHERE c.status='pending' ORDER BY c.created LIMIT 20").fetchall()
    txt='\n'.join(f"#{r['id']} | {r['user_id']} | {r['title']} | {r['points_cost']} نقطة" for r in rows) or 'لا توجد طلبات معلقة.'
    await state.set_state(Input.award_id)
    await m.answer('⚡ الطلبات المعلقة:\n'+txt+'\n\nللموافقة اكتب: approve 12\nللرفض وإرجاع النقاط اكتب: reject 12\nالموافقة تعني تسجيل التسليم الإداري فقط، ولا تنفذ تحويلات Ichancy.',reply_markup=back())

@router.message(Input.award_id)
async def award_finish(m:Message,state:FSMContext):
    try:
        action,raw=(m.text or '').strip().split()
        cid=int(raw)
        assert action in ('approve','reject')
    except (ValueError,AssertionError): return await m.answer('مثال: approve 12 أو reject 12')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        r=c.execute('SELECT * FROM claims WHERE id=? AND status=?',(cid,'pending')).fetchone()
        if not r: return await m.answer('الطلب غير موجود أو تمت معالجته سابقاً.')
        status='approved' if action=='approve' else 'rejected'
        c.execute('UPDATE claims SET status=?,resolved=CURRENT_TIMESTAMP WHERE id=?',(status,cid))
        if status=='rejected': c.execute('UPDATE users SET points=points+? WHERE id=?',(r['points_cost'],r['user_id']))
    audit(m.from_user.id,'claim_'+status,cid)
    await state.clear()
    await m.answer(f'تم تحديث الطلب #{cid} إلى {status}.',reply_markup=keyboard(LOYALTY_ADMIN_ROWS))
    try: await m.bot.send_message(r['user_id'],f'تحديث طلب جائزة الولاء #{cid}: {status}')
    except Exception: logging.exception('Notification failed')

@router.message(F.text == '👥 المستخدمين')
async def users(m:Message):
    if not admin(m.from_user): return
    with db() as c:
        total=c.execute('SELECT COUNT(*) n FROM users').fetchone()['n']
        banned=c.execute('SELECT COUNT(*) n FROM users WHERE banned=1').fetchone()['n']
    await m.answer(f'👥 عدد المستخدمين: {total}\n🚫 المحظورون: {banned}',reply_markup=keyboard(USER_ADMIN_ROWS))

@router.message(F.text == '📊 تقرير')
async def report(m:Message):
    if not admin(m.from_user): return
    with db() as c:
        total=c.execute('SELECT COUNT(*) n FROM users').fetchone()['n']
        pending=c.execute("SELECT COUNT(*) n FROM claims WHERE status='pending'").fetchone()['n']
        approved=c.execute("SELECT COUNT(*) n FROM claims WHERE status='approved'").fetchone()['n']
    await m.answer(f'📊 تقرير البوت\nالمستخدمون: {total}\nجوائز معلقة: {pending}\nجوائز معتمدة: {approved}\nالعمليات المالية الخارجية: غير مفعّلة')

@router.message(F.text == '🔎 البحث عن مستخدم')
async def lookup_start(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    await state.set_state(Input.lookup)
    await m.answer('أرسل Telegram ID أو اسم المستخدم.',reply_markup=back())

@router.message(Input.lookup)
async def lookup_finish(m:Message,state:FSMContext):
    query=(m.text or '').strip().lstrip('@')
    with db() as c:
        u=c.execute('SELECT * FROM users WHERE id=?' if query.isdigit() else 'SELECT * FROM users WHERE username=? COLLATE NOCASE',(int(query) if query.isdigit() else query,)).fetchone()
    await state.clear()
    if u: return await m.answer(f"👤 {u['first_name']} | {u['id']}",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='فتح ملف المستخدم',callback_data=f"ud:{u['id']}:0")]]))
    await m.answer('المستخدم غير موجود.',reply_markup=keyboard(ADMIN_ROWS))

@router.message(F.text.in_({'🚫 حظر مستخدم','🔓 فك حظر مستخدم'}))
async def ban_start(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    await state.set_state(Input.ban if m.text.startswith('🚫') else Input.unban)
    await m.answer('أرسل Telegram ID.',reply_markup=back())

@router.message(Input.ban)
@router.message(Input.unban)
async def ban_finish(m:Message,state:FSMContext):
    if not (m.text or '').isdigit(): return await m.answer('أرسل رقم المستخدم.')
    banned=1 if await state.get_state()==Input.ban.state else 0
    with db() as c: c.execute('UPDATE users SET banned=? WHERE id=?',(banned,int(m.text)))
    audit(m.from_user.id,'ban_change',f'{m.text}:{banned}')
    await notify_user(m.bot,int(m.text),'🚫 تم حظر حسابك من البوت بواسطة الإدارة.' if banned else '🔓 تم فك حظر حسابك بواسطة الإدارة.')
    await state.clear()
    await m.answer('تم تحديث حالة المستخدم.',reply_markup=keyboard(USER_ADMIN_ROWS))

@router.message(F.text == '⚙️ حالة البوت (تشغيل/إيقاف)')
async def toggle(m:Message):
    if not admin(m.from_user): return
    v='0' if setting('enabled')=='1' else '1'
    with db() as c: c.execute("UPDATE settings SET value=? WHERE key='enabled'",(v,))
    audit(m.from_user.id,'bot_enabled',v)
    await m.answer('البوت مفعّل' if v=='1' else 'البوت موقوف للمستخدمين (الأدمن يعمل).')

@router.message(F.text.in_({'📝 تعديل نص البونصات والعروض الحالية', '📝 تعديل نص العروض والبونصات'}))
async def bonus_start(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    await state.set_state(Input.bonus_text)
    await m.answer('أرسل نص العروض الجديد.',reply_markup=back())

@router.message(Input.bonus_text)
async def bonus_finish(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    if not (m.text or '').strip(): return await m.answer('أرسل نصاً غير فارغ.')
    with db() as c: c.execute("UPDATE settings SET value=? WHERE key='bonuses'",(m.text[:3000],))
    audit(m.from_user.id,'bonuses_updated')
    await state.clear()
    await m.answer('تم تحديث نص العروض.',reply_markup=keyboard(ADMIN_ROWS))

@router.message(F.text == '📢 الإذاعة')
async def broadcast_start(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    await state.set_state(Input.broadcast)
    await m.answer('أرسل رسالة الإذاعة. سيتم إرسالها للمستخدمين غير المحظورين.',reply_markup=back())

@router.message(Input.broadcast)
async def broadcast_finish(m:Message,state:FSMContext):
    if not m.text: return await m.answer('أرسل نصاً.')
    with db() as c: ids=[r['id'] for r in c.execute('SELECT id FROM users WHERE banned=0')]
    sent=0
    for uid in ids:
        try:
            await m.bot.send_message(uid,m.text[:4000]);sent+=1
        except Exception: pass
        await asyncio.sleep(0.05)
    audit(m.from_user.id,'broadcast',f'{sent}/{len(ids)}')
    await state.clear()
    await m.answer(f'تم الإرسال إلى {sent} من {len(ids)} مستخدم.',reply_markup=keyboard(ADMIN_ROWS))

def support_keyboard(confirm=False):
    rows=[]
    if confirm:
        rows.append([InlineKeyboardButton(text='☑️ تأكيد إرسال الرسالة',callback_data='support:send')])
    rows.append([InlineKeyboardButton(text='↪️ رجوع',callback_data='support:back')])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(F.text == '📝 رسالة للأدمن')
async def support_start(m:Message,state:FSMContext):
    await state.clear()
    await state.set_state(Input.support)
    await m.answer('''🗣️ <b>إرسال رسالة لدعم البوت</b>

يرجى تزويدنا بالمشكلة التي تواجهها أو كتابة رسالة بشكل تفصيلي تشرح سبب التواصل مع الدعم لكي يقوم فريق الدعم بالمساعدة الفورية.

<i>ينتظر البوت رسالة منك •••</i>''',parse_mode='HTML',reply_markup=support_keyboard())

@router.message(Input.support)
async def support_preview(m:Message,state:FSMContext):
    if not m.text or not m.text.strip():
        return await m.answer('يرجى كتابة رسالة نصية.',reply_markup=support_keyboard())
    body=m.text.strip()
    if len(body)>3500:
        return await m.answer('الرسالة طويلة. اختصرها إلى 3500 حرف كحد أقصى.')
    await state.update_data(support_body=body)
    await state.set_state(Input.support_confirm)
    from html import escape
    await m.answer('''🗣️ <b>مراسلة الدعم</b>

يرجى التأكد من الرسالة ومن ثم الضغط على زر إرسال

<b>الرسالة:</b>
'''+escape(body),parse_mode='HTML',reply_markup=support_keyboard(confirm=True))

@router.message(Input.support_confirm)
async def support_wait_confirm(m:Message):
    await m.answer('اضغط على «تأكيد إرسال الرسالة» لإرسالها، أو «رجوع» للإلغاء.',reply_markup=support_keyboard(confirm=True))

@router.callback_query(F.data.startswith('support:'))
async def support_action(q:CallbackQuery,state:FSMContext,bot:Bot):
    if q.data=='support:back':
        await state.clear()
        await q.answer()
        return await q.message.answer('🏠 القائمة الرئيسية',reply_markup=keyboard(ROWS))
    if q.data!='support:send': return await q.answer('زر غير معروف',show_alert=True)
    if await state.get_state()!=Input.support_confirm.state:
        return await q.answer('الرسالة غير جاهزة. اكتب رسالة جديدة.',show_alert=True)
    data=await state.get_data(); body=data.get('support_body','')
    if not body: return await q.answer('لا توجد رسالة للإرسال.',show_alert=True)
    if not SUPPORT_CHAT_ID:
        return await q.answer('مجموعة الدعم غير مهيأة.',show_alert=True)
    from html import escape
    sender=q.from_user
    username='@'+sender.username if sender.username else 'لا يوجد'
    text=(f'📨 <b>رسالة جديدة لدعم البوت</b>\n'
          f'👤 الاسم: {escape(sender.full_name)}\n'
          f'🆔 المعرف: <code>{sender.id}</code>\n'
          f'🔗 اسم المستخدم: {escape(username)}\n\n'
          f'💬 <b>الرسالة:</b>\n{escape(body)}')
    try:
        delivered=await bot.send_message(int(SUPPORT_CHAT_ID),text,parse_mode='HTML')
        with db() as c:
            c.execute('INSERT OR REPLACE INTO support_thread_map(chat_id,message_id,user_id) VALUES(?,?,?)',(delivered.chat.id,delivered.message_id,sender.id))
    except Exception:
        logging.exception('Failed to deliver support message to %s',SUPPORT_CHAT_ID)
        return await q.answer('تعذر الإرسال إلى مجموعة الدعم. حاول لاحقاً.',show_alert=True)
    await state.clear()
    await q.answer('تم الإرسال بنجاح')
    await q.message.answer('✅ تم إرسال رسالتك إلى فريق الدعم بنجاح. سيتم مراجعتها.',reply_markup=keyboard(ROWS))

def referral_metrics(uid):
    # Only site transactions explicitly verified by admins are counted. Local bot deposits are NOT site play.
    with db() as c:
        refs=c.execute('SELECT id,first_name,username FROM users WHERE referrer=? ORDER BY joined DESC',(uid,)).fetchall()
        summary=[]
        for r in refs:
            ops=c.execute('SELECT kind,amount,activity_day FROM referral_finance WHERE referred_id=?',(r['id'],)).fetchall()
            deposits=sum(x['amount'] for x in ops if x['kind']=='deposit')
            withdrawals=sum(x['amount'] for x in ops if x['kind']=='withdraw')
            transfer_days={x['activity_day'] for x in ops if x['kind']=='deposit'}
            active=len([x for x in ops if x['kind']=='deposit'])>=int(setting('referral_min_transfers') or 3) and len(transfer_days)>=int(setting('referral_min_days') or 3) and deposits>=withdrawals and deposits>0
            suspicious=withdrawals>deposits and withdrawals>0
            summary.append(dict(id=r['id'],name=r['first_name'] or r['username'] or str(r['id']),deposit=deposits,withdraw=withdrawals,active=active and not suspicious,suspicious=suspicious))
        commissions=c.execute("SELECT amount,status FROM referral_commissions WHERE referrer_id=?",(uid,)).fetchall()
    return summary,commissions

def referral_keyboard():
    labels=[('📋 نسخ رابط الدعوة','ref:copy'),('📤 مشاركة الرابط','ref:share'),('👥 تفاصيل إحالاتي','ref:details'),('💸 حالة إحالاتي','ref:status'),('📊 إحصائيات متقدمة','ref:stats'),('🏠 القائمة الرئيسية','ref:home')]
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a,callback_data=b) for a,b in labels[i:i+2]] for i in (0,2)]+[[InlineKeyboardButton(text=labels[4][0],callback_data=labels[4][1])],[InlineKeyboardButton(text=labels[5][0],callback_data=labels[5][1])]])

async def referral_screen(message,bot,uid):
    me=await bot.get_me(); link=f'https://t.me/{me.username}?start=ref_{uid}'
    refs,com=referral_metrics(uid); active=sum(x['active'] for x in refs); suspicious=sum(x['suspicious'] for x in refs)
    need=int(setting('referral_min_active') or 3)
    earned=sum(x['amount'] for x in com); paid=sum(x['amount'] for x in com if x['status']=='paid')
    body=(f'🥉 <b>نظام الإحالات المتقدم</b> 🥉\n━━━━━━━━━━━━━━━━━━━━━\n\n🔗 <b>رابط الإحالة الخاص بك:</b>\n{link}\n\n━━━━━━━━━━━━━━━━━━━━━\n📊 <b>لوحة التحكم:</b>\n\n👥 إجمالي الإحالات: <b>{len(refs)}</b>\n✅ إحالات نشطة: <b>{active}</b> من <b>{need}</b> مطلوبة للصرف (تنقصك {max(0,need-active)})\n⏳ إحالات قيد التفعيل: <b>{len(refs)-active-suspicious}</b>\n🏅 مستواك: <b>🥉 برونزي</b>\n\n━━━━━━━━━━━━━━━━━━━━━\n💰 <b>العمولات:</b>\n\n📌 تفاصيل نسب ومبالغ العمولة متاحة للإدارة فقط\n\n━━━━━━━━━━━━━━━━━━━━━\n📌 <b>شروط استحقاق العمولة:</b>\n• يلزم {need} إحالات نشطة على الأقل\n• الإحالة تنشط بعد {setting("referral_min_transfers")} تحويلات للموقع خلال {setting("referral_min_days")} أيام مختلفة\n• الإحالة التي تسحب أكثر مما تودع تُعلّم للمراجعة ولا تُحتسب\n\n🛡️ <b>نظام الحماية:</b>\n• فترة نضج {setting("referral_maturity_days")} أيام قبل الصرف\n• الحد الشهري {setting("referral_monthly_cap")} NSP لكل إحالة\n• مراجعة العمليات المشبوهة من الإدارة\n\n━━━━━━━━━━━━━━━━━━━━━\n💡 <b>كيف يعمل النظام:</b>\n1️⃣ شارك رابطك مع أصدقائك\n2️⃣ يسجّلون عبر الرابط\n3️⃣ تتحقق الإدارة من نشاطهم على الموقع\n4️⃣ الإدارة تسجّل وتوزّع العمولات وفق سجلات موثّقة')
    await message.answer(body,parse_mode='HTML',reply_markup=referral_keyboard())

@router.callback_query(F.data.startswith('ref:'))
async def referral_click(q:CallbackQuery,bot:Bot,state:FSMContext):
    if not await require_join(bot,q.from_user.id,q.message): return await q.answer()
    await q.answer(); action=q.data[4:]; uid=q.from_user.id
    me=await bot.get_me(); link=f'https://t.me/{me.username}?start=ref_{uid}'
    if action=='home': return await home(q.message)
    if action=='copy': return await q.message.answer('📋 رابطك للنسخ:\n'+link)
    if action=='share': return await q.message.answer('📤 شارك الرابط التالي مع أصدقائك:\n'+link)
    refs,com=referral_metrics(uid)
    if action=='details':
        if not refs: return await q.message.answer('📭 لا توجد إحالات بعد.\nشارك رابطك لبدء كسب العمولات!')
        lines=['👥 تفاصيل إحالاتي']
        for r in refs[:30]: lines.append(f"• {r['name']} ({r['id']}) — {'🔴 قيد المراجعة' if r['suspicious'] else '🟢 نشطة' if r['active'] else '🟡 قيد التفعيل'}")
        return await q.message.answer('\n'.join(lines))
    if action=='status':
        active=sum(r['active'] for r in refs); need=int(setting('referral_min_active') or 3)
        return await q.message.answer(f'💸 حالة الإحالات\nالإحالات النشطة: {active}/{need}\nتُدار تفاصيل العمولات من لوحة الإدارة فقط.')
    if action=='stats':
        d=sum(r['deposit'] for r in refs); w=sum(r['withdraw'] for r in refs); net=max(0,d-w)
        e=sum(c['amount'] for c in com); paid=sum(c['amount'] for c in com if c['status']=='paid')
        return await q.message.answer(f'📊 <b>إحصائيات متقدمة</b>\n━━━━━━━━━━━━━━━━━━━━━\n📈 <b>ملخص مالي (عمليات موقع موثقة إدارياً):</b>\n💸 إجمالي ما أودعه المُحالون للموقع: {d} NSP\n💰 إجمالي ما سحبوه من الموقع: {w} NSP\n📉 الخسارة الصافية الإجمالية: {net} NSP\n📊 متوسط الخسارة لكل إحالة: {net//len(refs) if refs else 0} NSP\n━━━━━━━━━━━━━━━━━━━━━\n💰 <b>ملخص العمولات:</b>\n🔒 تفاصيل العمولات خاصة بالإدارة\n━━━━━━━━━━━━━━━━━━━━━\n👥 <b>حالة الإحالات:</b>\n🟢 نشطة: {sum(r["active"] for r in refs)} | 🟡 قيد التفعيل: {sum(not r["active"] and not r["suspicious"] for r in refs)} | 🔴 موقوفة/مشبوهة: {sum(r["suspicious"] for r in refs)}\n━━━━━━━━━━━━━━━━━━━━━\n📅 حد أقصى شهري: {setting("referral_monthly_cap")} NSP / إحالة\n🏆 حد أقصى كلي: {setting("referral_total_cap")} NSP / إحالة',parse_mode='HTML')

@router.message(F.text.in_(ALL))
async def services(m:Message,bot:Bot):
    save(m.from_user)
    with db() as c: u=c.execute('SELECT banned FROM users WHERE id=?',(m.from_user.id,)).fetchone()
    if u and u['banned']: return await m.answer('حسابك محظور من استخدام الخدمات.')
    if setting('enabled')!='1' and not admin(m.from_user): return await m.answer('البوت متوقف مؤقتاً.')
    if m.text=='💸 نظام الإحالات':
        return await referral_screen(m,bot,m.from_user.id)
    if m.text=='🎁 البونصات والعروض الحالية': return await m.answer(setting('bonuses'))
    if m.text=='🟥 Ichancy': return await m.answer('خدمات Ichancy الخارجية غير متصلة حالياً؛ بانتظار الربط الرسمي.')
    if m.text=='💸 شحن رصيد البوت': return await deposit_menu(m)
    if m.text=='💰 سحب رصيد البوت': return await withdrawal_menu(m,m.from_user.id)
    lookup={'💜 الشروط والأحكام':'terms','⚠️ الشروحات':'tutorials','💵 اللفة المجانية':'free_spin','💌 تواصل معنا':'contact_url','↗️ Vpn لتشغيل كامل أقسام الموقع':'vpn_url','↗️ ichancy apk':'apk_url','🎰 ألعاب Ichancy':'games_url','⭐ دخول مباشر للألعاب':'direct_url'}
    if m.text in lookup:
        val=setting(lookup[m.text]); return await m.answer(val or 'لم يضف الأدمن محتوى هذا القسم بعد.',reply_markup=keyboard([['🏠 القائمة الرئيسية']]))
    if m.text=='✅ السجل':
        with db() as c: rows=c.execute('SELECT delta,balance_after,created FROM bot_ledger WHERE user_id=? ORDER BY id DESC LIMIT 15',(m.from_user.id,)).fetchall()
        return await m.answer('📜 سجل رصيد البوت الداخلي\n'+('\n'.join(f"{r['created']} | {r['delta']:+} | {r['balance_after']}" for r in rows) or 'لا توجد عمليات'))
    await m.answer('هذا القسم معلوماتي فقط، وليس متصلاً بـ Ichancy.')

@router.message(F.text.in_(ADMIN_ALL))
async def admin_placeholder(m:Message):
    if not admin(m.from_user): return
    await m.answer(f'{m.text}\n\n🛠️ هذا القسم ظاهر حسب التصميم المرجعي، لكنه غير مفعّل بعد. لا تتم أي حركة مالية أو سحب بيانات غير مصرح به.')

def user_list_markup(page, total, records):
    rows=[]
    for u in records:
        name=(u['first_name'] or u['username'] or 'مستخدم').replace('\n',' ')[:28]
        rows.append([InlineKeyboardButton(text=f"👤 {name} | {u['id']}",callback_data=f"ud:{u['id']}:{page}")])
    nav=[]
    if page>0: nav.append(InlineKeyboardButton(text='⬅️ السابق',callback_data=f'ul:{page-1}'))
    if (page+1)*8<total: nav.append(InlineKeyboardButton(text='التالي ➡️',callback_data=f'ul:{page+1}'))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(text='↩️ لوحة الأدمن',callback_data=BUTTON_IDS['↩️ رجوع للوحة الأدمن'])])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def show_user_list(message, page=0):
    with db() as c:
        total=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        page=max(0,min(page,max(0,(total-1)//8)))
        rows=c.execute('SELECT id,username,first_name FROM users ORDER BY joined DESC,id DESC LIMIT 8 OFFSET ?', (page*8,)).fetchall()
    txt=f'👥 المستخدمون: {total}\nاضغط على اسم المستخدم لفتح ملفه.\nالصفحة {page+1} من {max(1,(total+7)//8)}'
    await message.edit_text(txt,reply_markup=user_list_markup(page,total,rows))

async def show_user_detail(message, uid, page=0):
    with db() as c:
        u=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
    if not u: return await message.edit_text('المستخدم غير موجود.',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='↩️ المستخدمون',callback_data=f'ul:{page}')]]))
    txt=(f"👤 {u['first_name'] or 'بدون اسم'}\n🔖 @{u['username'] or 'بدون يوزر'}\n🆔 {uid}\n"
         f"💰 رصيد البوت الداخلي: {u['bot_balance']}\n🌟 نقاط الولاء: {u['points']}\n"
         f"🚫 الحالة: {'محظور' if u['banned'] else 'نشط'}\n📅 التسجيل: {u['joined']}\n\nالرصيد هنا داخلي وليس رصيد Ichancy.")
    rows=[
        [InlineKeyboardButton(text='➕ إضافة رصيد',callback_data=f'ua:credit:{uid}:{page}'),InlineKeyboardButton(text='➖ خصم رصيد',callback_data=f'ua:debit:{uid}:{page}')],
        [InlineKeyboardButton(text='➕ إضافة نقاط',callback_data=f'ua:points:{uid}:{page}'),InlineKeyboardButton(text='➖ خصم نقاط',callback_data=f'ua:points_debit:{uid}:{page}')],
        [InlineKeyboardButton(text='📜 سجل العمليات',callback_data=f'ua:history:{uid}:{page}')],
        [InlineKeyboardButton(text='🔓 فك الحظر' if u['banned'] else '🚫 حظر المستخدم',callback_data=f'ua:ban:{uid}:{page}')],
        [InlineKeyboardButton(text='↩️ قائمة المستخدمين',callback_data=f'ul:{page}')]
    ]
    await message.edit_text(txt,reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

async def user_callback(q,state):
    parts=q.data.split(':')
    if parts[0]=='ul': return await show_user_list(q.message,int(parts[1]))
    if parts[0]=='ud': return await show_user_detail(q.message,int(parts[1]),int(parts[2]))
    if parts[0]=='uc':
        await state.clear()
        return await show_user_detail(q.message,int(parts[1]),int(parts[2]))
    action,uid,page=parts[1],int(parts[2]),int(parts[3])
    if action=='ban':
        with db() as c:
            row=c.execute('SELECT banned FROM users WHERE id=?',(uid,)).fetchone()
            if row: c.execute('UPDATE users SET banned=? WHERE id=?',(1-int(row['banned']),uid))
        audit(q.from_user.id,'user_ban_toggle',uid)
        await notify_user(q.bot,uid,'🚫 تم حظر حسابك من البوت بواسطة الإدارة.' if row and not int(row['banned']) else '🔓 تم فك حظر حسابك بواسطة الإدارة.')
        return await show_user_detail(q.message,uid,page)
    if action=='history':
        with db() as c: rows=c.execute('SELECT delta,balance_after,created FROM bot_ledger WHERE user_id=? ORDER BY id DESC LIMIT 12',(uid,)).fetchall()
        lines='\n'.join(f"{r['created']}: {r['delta']:+d} → {r['balance_after']}" for r in rows) or 'لا توجد عمليات'
        return await q.message.edit_text(f'📜 سجل رصيد البوت للمستخدم {uid}\n{lines}',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='↩️ ملف المستخدم',callback_data=f'ud:{uid}:{page}')]]))
    if action in ('credit','debit','points','points_debit'):
        await state.set_state(Input.points_change if action in ('points','points_debit') else Input.balance_change)
        await state.update_data(target_uid=uid,action=action,page=page)
        await q.message.edit_text(f"{'🌟 تعديل نقاط الولاء' if action in ('points','points_debit') else '💰 تعديل رصيد البوت'} للمستخدم {uid}\nأرسل المبلغ كعدد صحيح أكبر من صفر، ولا يتجاوز رصيد المستخدم عند الخصم.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='↩️ إلغاء',callback_data=f'uc:{uid}:{page}')]]))

@router.message(Input.balance_change)
@router.message(Input.points_change)
async def apply_internal_change(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    data=await state.get_data()
    try:
        amount=int((m.text or '').strip())
        if not 0<amount<=9223372036854775807: raise ValueError()
    except ValueError: return await m.answer('أرسل عدداً صحيحاً موجباً ضمن الحد المسموح.')
    uid,action,page=data['target_uid'],data['action'],data['page']
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT bot_balance,points FROM users WHERE id=?',(uid,)).fetchone()
        if not row: return await m.answer('المستخدم غير موجود.')
        if action in ('points','points_debit'):
            new=row['points'] + (amount if action=='points' else -amount)
            if new<0: return await m.answer(f'❌ المستخدم يملك {row["points"]:,} نقطة فقط، لا يمكن خصم أكثر منها.')
            if new>9223372036854775807: return await m.answer('❌ تجاوز الحد التقني لقاعدة البيانات.')
            c.execute('UPDATE users SET points=? WHERE id=?',(new,uid))
        else:
            delta=amount if action=='credit' else -amount
            new=row['bot_balance']+delta
            if new<0: return await m.answer(f'❌ رصيد المستخدم {row["bot_balance"]:,} فقط، لا يمكن خصم أكثر منه.')
            if new>9223372036854775807: return await m.answer('❌ تجاوز الحد التقني لقاعدة البيانات.')
            c.execute('UPDATE users SET bot_balance=? WHERE id=?',(new,uid))
            c.execute('INSERT INTO bot_ledger(user_id,admin_id,delta,balance_after) VALUES(?,?,?,?)',(uid,m.from_user.id,delta,new))
    audit(m.from_user.id,'internal_'+action,f'{uid}:{amount}')
    if action in ('points','points_debit'):
        notice=f'🌟 عدّلت الإدارة نقاط ولائك: {"+" if action=="points" else "-"}{amount} نقطة.\nرصيد النقاط الحالي: {new}'
    else:
        notice=f'💰 عدّلت الإدارة رصيدك الداخلي: {"إضافة" if action=="credit" else "خصم"} {amount}.\nالرصيد الحالي: {new}'
    await notify_user(m.bot,uid,notice)
    await state.clear()
    await m.answer(f'✅ تمت العملية داخل البوت فقط. الرصيد/النقاط الجديدة: {new}\nلا يوجد أي تحويل إلى Ichancy.',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='↩️ ملف المستخدم',callback_data=f'ud:{uid}:{page}')]]))


# All balances in these handlers are LOCAL bot ledger balances; no Ichancy operations.
def add_local_balance(c,uid,delta,actor):
    row=c.execute('SELECT bot_balance FROM users WHERE id=?',(uid,)).fetchone()
    if not row or not 0 <= row['bot_balance']+delta <= 9223372036854775807: raise ValueError('المستخدم غير موجود أو الرصيد غير كافٍ أو المبلغ كبير جداً')
    new=row['bot_balance']+delta
    c.execute('UPDATE users SET bot_balance=? WHERE id=?',(new,uid))
    c.execute('INSERT INTO bot_ledger(user_id,admin_id,delta,balance_after) VALUES(?,?,?,?)',(uid,actor,delta,new))
    return new

@router.message(F.text=='🎟️ إهداء رصيد')
async def transfer_start(m:Message,state:FSMContext):
    await state.set_state(Input.user_transfer)
    await m.answer('🎟️ إهداء رصيد البوت الداخلي\nأرسل: Telegram_ID المبلغ\nمثال: 123456789 50\nالتحويل نهائي، ولا يمس رصيد Ichancy.')

@router.message(Input.user_transfer)
async def transfer_finish(m:Message,state:FSMContext):
    try:
        uid,amount=map(int,(m.text or '').split()); assert 0<amount<=100000000 and uid!=m.from_user.id
    except (ValueError,AssertionError): return await m.answer('أرسل رقم المستخدم والمبلغ الصحيح.')
    try:
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not c.execute('SELECT id FROM users WHERE id=? AND banned=0',(m.from_user.id,)).fetchone(): raise ValueError('حسابك غير متاح')
            if not c.execute('SELECT id FROM users WHERE id=? AND banned=0',(uid,)).fetchone(): raise ValueError('المستلم غير مسجل أو محظور')
            add_local_balance(c,m.from_user.id,-amount,m.from_user.id)
            add_local_balance(c,uid,amount,m.from_user.id)
    except ValueError as e: return await m.answer(str(e))
    await state.clear()
    await m.answer(f'✅ تم تحويل {amount} من رصيد البوت الداخلي إلى {uid}.')
    try: await m.bot.send_message(uid,f'🎟️ وصلك إهداء {amount} من رصيد البوت الداخلي.')
    except Exception: pass

@router.message(F.text=='🎁 كود هدية')
async def gift_start(m:Message,state:FSMContext):
    await state.set_state(Input.gift_redeem)
    await m.answer('🎁 أرسل كود الهدية للحصول على رصيد داخلي في البوت.')

async def redeem_code(uid,code,message):
    code=''.join(code.strip().upper().split())
    try:
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute('SELECT amount,max_uses,uses FROM gift_codes WHERE code=?',(code,)).fetchone()
            if not r and not code.endswith('SHEIKH'):
                code=code+'SHEIKH'
                r=c.execute('SELECT amount,max_uses,uses FROM gift_codes WHERE code=?',(code,)).fetchone()
            if not r or r['uses']>=r['max_uses']: raise ValueError('الكود غير موجود أو انتهت صلاحيته.')
            if c.execute('SELECT 1 FROM gift_redemptions WHERE code=? AND user_id=?',(code,uid)).fetchone(): raise ValueError('استخدمت هذا الكود سابقاً.')
            if not c.execute('SELECT 1 FROM users WHERE id=? AND banned=0',(uid,)).fetchone(): raise ValueError('الحساب غير متاح.')
            c.execute('INSERT INTO gift_redemptions(code,user_id) VALUES(?,?)',(code,uid))
            c.execute('UPDATE gift_codes SET uses=uses+1 WHERE code=?',(code,))
            new=add_local_balance(c,uid,r['amount'],0)
    except ValueError as e: return await message.answer(str(e))
    await message.answer(f'🎁 تم إضافة {r["amount"]} رصيد داخلي. رصيدك الآن {new}.')

@router.message(Input.gift_redeem)
async def gift_finish(m:Message,state:FSMContext):
    await state.clear()
    if not await require_join(m.bot,m.from_user.id,m): return
    save(m.from_user)
    await redeem_code(m.from_user.id,m.text or '',m)

ADMIN_ACTIONS={
 '⚙️ تعديل سعر الدولار':('dollar_rate','أرسل سعر 1 ShamCash USD بالليرة السورية الجديدة (رقم موجب). سيظهر السعر في رسالة شام كاش فقط.'),
 '💸 الكاش باك الأسبوعي 10%':('cashback','أرسل نسبة الكاش باك للعرض (0 إلى 100).'),
 '💰 توزيع أرباح الإحالات':('referral_reward','أرسل مكافأة الإحالة الداخلية لكل مستخدم جديد (0 لتعطيلها).'),
 '💳 تعديل أكواد شام كاش':('sham_codes','أرسل نص أكواد شام كاش.'),
 '💳 تعديل أكواد سيريتل كاش':('syriatel_codes','أرسل نص أكواد سيريتل كاش.'),
 '🎁 إدارة الجائزة الحالية':('current_prize','أرسل وصف الجائزة الحالية.'),
 '🎁 إضافة أو حذف البونص':('bonuses','أرسل نص البونصات الجديد.'),
 '📝 تعديل نص البونصات والعروض الحالية':('bonuses','أرسل نص البونصات الجديد.'),
 '📝 تعديل نص العروض والبونصات':('bonuses','أرسل نص العروض والبونصات الجديد.'),
 '🔥 حرق رقم عملية':('burned_operation','أرسل رقم العملية للتسجيل الإداري فقط (لا يؤثر على Ichancy).'),
}

def admin_actions_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text='📋 إدارة المحتوى والروابط',callback_data='ac:content')],
      [InlineKeyboardButton(text='↩️ رجوع للوحة الأدمن',callback_data=BUTTON_IDS['↩️ رجوع للوحة الأدمن'])]])

async def admin_action(message,state,user,action):
    if action in ('content','📝 إدارة المحتوى والروابط'):
        keys=[('شروط الاستخدام','terms'),('الشروحات','tutorials'),('رابط التواصل','contact_url'),('رابط VPN','vpn_url'),('رابط APK','apk_url'),('رابط الألعاب','games_url'),('الدخول المباشر','direct_url'),('اللفة المجانية','free_spin')]
        return await message.edit_text('📝 تعديل محتوى الأقسام والروابط',reply_markup=InlineKeyboardMarkup(inline_keyboard=[*[ [InlineKeyboardButton(text=label,callback_data='ac:cfg:'+key)] for label,key in keys], [InlineKeyboardButton(text='↩️ لوحة الأدمن',callback_data=BUTTON_IDS['↩️ رجوع للوحة الأدمن'])]]))
    if action.startswith('cfg:'):
        key=action[4:]
        await state.set_state(Input.admin_config)
        await state.update_data(config_key=key)
        return await message.answer(f'أرسل القيمة الجديدة لـ {key}.')
    if action in ADMIN_ACTIONS:
        key,prompt=ADMIN_ACTIONS[action]
        await state.set_state(Input.admin_config)
        await state.update_data(config_key=key)
        return await message.answer(prompt)
    if action=='⚙️ إعدادات نظام الإحالات':
        fields=[('نسبة العمولة (للأدمن فقط)','referral_percent'),('الحد الأدنى للإحالات النشطة','referral_min_active'),('عدد تحويلات التفعيل','referral_min_transfers'),('عدد أيام النشاط','referral_min_days'),('فترة النضج بالأيام','referral_maturity_days'),('السقف الشهري','referral_monthly_cap'),('السقف الكلي','referral_total_cap')]
        return await message.answer('⚙️ إعدادات الإحالات — خاصة بالإدارة\n'+'\n'.join(f'{title}: {setting(key)}' for title,key in fields),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=title,callback_data='ac:cfg:'+key)] for title,key in fields]))
    if action=='📋 سجل إحالات البوت':
        with db() as c: rows=c.execute('SELECT referrer,COUNT(*) n FROM users WHERE referrer IS NOT NULL GROUP BY referrer ORDER BY n DESC LIMIT 20').fetchall()
        return await message.answer('📋 عدد الإحالات المسجلة\n'+('\n'.join(str(r['referrer'])+': '+str(r['n']) for r in rows) or 'لا توجد إحالات.'))
    if action=='🎟️ إضافة كود':
        await state.set_state(Input.admin_code)
        return await message.answer('🎟️ أرسل اسم الكود فقط، مثال: code\nسيُضاف اسم Sheikh تلقائياً للكود.')
    if action=='📊 تقرير':
        with db() as c:
            total=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]; pending=c.execute("SELECT COUNT(*) FROM claims WHERE status='pending'").fetchone()[0]
        return await message.answer(f'📊 المستخدمون: {total}\n🎁 جوائز معلقة: {pending}')
    if action=='🔎 البحث عن مستخدم': return await admin_search_start(message,state)
    if action=='📜 سجل مستخدم': return await admin_search_start(message,state)
    if action=='➕ إضافة رصيد' or action=='➖ خصم رصيد' or action in ('🚫 حظر مستخدم','🔓 فك حظر مستخدم'):
        return await message.answer('اختر المستخدم أولاً من 👥 المستخدمين، ثم نفّذ العملية من ملفه.')

    if action=='⚙️ حالة البوت (تشغيل/إيقاف)':
        v='0' if setting('enabled')=='1' else '1'
        with db() as c: c.execute("UPDATE settings SET value=? WHERE key='enabled'",(v,))
        audit(user.id,'bot_enabled',v)
        return await message.answer('✅ البوت مفعّل' if v=='1' else '⏸️ البوت متوقف للمستخدمين')
    if action=='🌟 إدارة نقاط الولاء': return await message.answer('🌟 لوحة الولاء',reply_markup=keyboard(LOYALTY_ADMIN_ROWS))
    if action=='➕ منح نقاط ولاء': return await add_start(message,state)
    if action=='➖ خصم نقاط ولاء': return await subtract_points_start(message,state)
    if action=='🎁 تعديل جوائز نقاط الولاء': return await loyalty_prizes_admin(message,state)
    if action=='⚡ تعجيل جوائز نقاط الولاء': return await awards(message,state)
    if action=='📢 الإذاعة': return await broadcast_start(message,state)
    if action in ('📝 تعديل نص البونصات والعروض الحالية', '📝 تعديل نص العروض والبونصات'): return await bonus_start(message,state)
    return await message.answer('هذه العملية غير مدعومة دون تكامل رسمي؛ لم يتم تنفيذ أي تغيير مالي خارجي.')

@router.message(Input.admin_config)
async def admin_config_finish(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    data=await state.get_data(); key=data['config_key']; value=(m.text or '').strip()
    if not value or len(value)>3500: return await m.answer('أرسل قيمة نصية لا تتجاوز 3500 حرف.')
    if key in ('dollar_rate','cashback','referral_reward','referral_percent','referral_min_active','referral_min_transfers','referral_min_days','referral_maturity_days','referral_monthly_cap','referral_total_cap'):
        try:
            v=float(value)
            if v<0 or (key=='dollar_rate' and v<=0) or (key in ('cashback','referral_percent') and v>100) or (key.startswith('referral_') and key!='referral_percent' and not v.is_integer()): raise ValueError()
        except ValueError: return await m.answer('القيمة الرقمية غير صحيحة.')
    with db() as c: c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))
    audit(m.from_user.id,'config_updated',key)
    await state.clear()
    await m.answer('✅ تم حفظ التعديل داخل البوت.',reply_markup=admin_actions_keyboard())

@router.message(Input.admin_code)
async def admin_code_name(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    raw=(m.text or '').strip()
    if not (1<=len(raw)<=30 and raw.isascii() and raw.isalnum()):
        return await m.answer('أرسل اسماً إنجليزياً أو أرقاماً فقط، بدون فراغات، بحد أقصى 30 حرفاً.')
    code=raw.upper()+'SHEIKH'
    with db() as c:
        if c.execute('SELECT 1 FROM gift_codes WHERE code=?',(code,)).fetchone():
            return await m.answer('الكود موجود مسبقاً، اختر اسماً مختلفاً.')
    await state.update_data(gift_code_name=code)
    await state.set_state(Input.admin_code_amount)
    await m.answer(f'🎟️ الكود: {code}\n💰 أدخل قيمة الكود بالرصيد الداخلي:')

@router.message(Input.admin_code_amount)
async def admin_code_amount(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    try:
        amount=int((m.text or '').strip())
        if not 0<amount<=9223372036854775807: raise ValueError()
    except ValueError:
        return await m.answer('أدخل قيمة صحيحة موجبة.')
    await state.update_data(gift_code_amount=amount)
    await state.set_state(Input.admin_code_uses)
    await m.answer('👥 هذا الكود صالح لكم شخص؟ أرسل العدد:')

@router.message(Input.admin_code_uses)
async def admin_code_uses(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    try:
        uses=int((m.text or '').strip())
        if not 0<uses<=100000: raise ValueError()
    except ValueError:
        return await m.answer('أدخل عدد مستخدمين صحيحاً وموجباً.')
    data=await state.get_data(); code=data['gift_code_name']; amount=data['gift_code_amount']
    try:
        with db() as c:
            c.execute('INSERT INTO gift_codes(code,amount,max_uses) VALUES(?,?,?)',(code,amount,uses))
    except sqlite3.IntegrityError:
        await state.clear()
        return await m.answer('الكود موجود مسبقاً، أعد المحاولة.')
    audit(m.from_user.id,'gift_code_created',f'{code}:{amount}:{uses}')
    await state.clear()
    await m.answer(f'✅ تم إنشاء كود الهدية\n🎟️ {code}\n💰 القيمة: {amount}\n👥 عدد المستخدمين: {uses}\nالرصيد داخلي فقط.',reply_markup=keyboard(CODE_ADMIN_ROWS))

async def notify_user(bot, uid, text):
    try:
        await bot.send_message(uid,text)
    except Exception:
        logging.info('User notification not delivered for %s (bot may be blocked)',uid)

async def admin_search_start(m,state):
    await state.set_state(Input.lookup)
    await m.answer('أرسل Telegram ID أو اسم المستخدم للبحث.')

async def handle_support_reply(m:Message):
    # Telegram groups: reply directly to the forwarded support message.
    # A channel post can only be answered by a channel administrator via channel posting.
    if not SUPPORT_CHAT_ID or str(m.chat.id)!=SUPPORT_CHAT_ID: return
    if not m.reply_to_message or not m.text or not m.text.strip(): return
    if m.from_user and m.from_user.is_bot: return
    # For group replies, require explicit admin ID; for channel posts, the channel identity is the sender.
    is_channel=m.chat.type=='channel'
    if not is_channel and (not m.from_user or m.from_user.id not in ADMIN_IDS): return
    with db() as c:
        target=c.execute('SELECT user_id FROM support_thread_map WHERE chat_id=? AND message_id=?',(m.chat.id,m.reply_to_message.message_id)).fetchone()
    if not target: return
    try:
        await m.bot.send_message(target['user_id'],'💬 رد فريق الدعم على رسالتك:\n\n'+m.text[:3800])
    except Exception:
        logging.exception('Support reply delivery failed')
        return await m.reply('❌ تعذّر إيصال الرد للمستخدم. قد يكون حظر البوت.')
    await m.reply('✅ تم إرسال الرد للمستخدم.')

@router.message(F.chat.id == int(SUPPORT_CHAT_ID) if SUPPORT_CHAT_ID.lstrip('-').isdigit() else F.chat.id == 0)
async def support_group_reply(m:Message):
    await handle_support_reply(m)

@router.channel_post()
async def support_channel_reply(m:Message):
    await handle_support_reply(m)

@router.message()
async def fallback(m:Message):
    await m.answer('استخدم أزرار القائمة أو اكتب /start.')

class MembershipMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, Message) and event.from_user and not admin(event.from_user):
            if not (event.text or '').startswith('/start'):
                if not await require_join(data['bot'],event.from_user.id,event): return None
        return await handler(event,data)

async def main():
    if not TOKEN: raise RuntimeError('Missing BOT_TOKEN')
    logging.basicConfig(level=logging.INFO)
    init()
    bot=Bot(TOKEN)
    await bot.set_my_commands([
        BotCommand(command='start', description='🏠 القائمة الرئيسية'),
        BotCommand(command='balance', description='💰 رصيدي في البوت'),
        BotCommand(command='cancel', description='❌ إلغاء العملية الحالية'),
    ], scope=BotCommandScopeDefault())
    dp=Dispatcher()
    router.message.middleware(MembershipMiddleware())
    dp.include_router(router)
    try: await dp.start_polling(bot)
    finally: await bot.session.close()

if __name__=='__main__': asyncio.run(main())
