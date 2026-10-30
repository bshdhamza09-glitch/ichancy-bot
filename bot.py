"""Sheikh Telegram bot. Local loyalty ledger; no Ichancy financial API calls."""
import asyncio
import logging
import re
import os, secrets
import sqlite3
import time
import aiohttp
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router, BaseMiddleware
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton, WebAppInfo, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton,
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
# Admin notifications (e.g. someone redeemed a fee-free withdrawal). Defaults to the withdrawal-requests channel.
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '').strip() or WITHDRAWAL_CHAT_ID
SUPPORT_CHAT_ID = os.getenv('SUPPORT_CHAT_ID', '-1004401691217').strip()
# Withdrawal-refund requests are delivered to this channel (override with REFUND_CHAT_ID in Railway).
REFUND_CHAT_ID = os.getenv('REFUND_CHAT_ID', '-1004294689688').strip()
REFUND_LABEL = '↩️ استرداد آخر طلب سحب'
LEGACY_BONUS_LABEL = '🎁 البونصات والعروض الحالية'  # removed from the menu; kept only so old inline buttons still resolve
DIST_LABEL = '📤 توزيع الإحالات'  # admin button (first row of the admin panel + referral admin menu)
SHAM_MAX_WITHDRAW = 50000  # default per Sham Cash request; editable from admin: setting sham_max_withdraw
PENDING_LABEL = '📋 الطلبات المعلّقة'
FEES_LABEL = '💸 عمولة وحدود السحب'
SUPPORT_USERNAME = '@Al_Basha_Ropert'
NO_EXPIRY_TS = 4102444800  # 2100-01-01: wheel cashback has no 24h expiry, it is single-use
SHAM_ACCOUNT = os.getenv('SHAM_ACCOUNT', 'bbcbfd15ad74579eb0b8e9baca872e57').strip()
SYRIATEL_ACCOUNT = os.getenv('SYRIATEL_ACCOUNT', '0933185350').strip()
QR = Path(__file__).with_name('sham_qr.jpg')
API_SYRIA_KEY = os.getenv('API_SYRIA_KEY', '').strip()
API_SYRIA_URL = 'https://apisyria.com/api/v1'
API_SYRIA_SYRIATEL_GSM = os.getenv('API_SYRIA_SYRIATEL_GSM', SYRIATEL_ACCOUNT).strip()
API_SYRIA_SHAM_ADDRESS = os.getenv('API_SYRIA_SHAM_ADDRESS', SHAM_ACCOUNT).strip()



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
    [REFUND_LABEL],
    ['🎰 ألعاب Ichancy', '⭐ دخول مباشر للألعاب'],
    ['🌟 نقاط الولاء'],
]
ADMIN_ROWS = [
    [DIST_LABEL, PENDING_LABEL],
    ['👥 المستخدمين', '🌟 إدارة نقاط الولاء'],
    ['💰 الإحالات', '🎟️ الأكواد'],
    ['⚙️ إعدادات البوت', '📊 التقارير'],
    ['📢 الإذاعة'],
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
    [FEES_LABEL],
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
REFERRAL_ADMIN_ROWS = [[DIST_LABEL], ['⚙️ إعدادات نظام الإحالات'], ['📋 سجل إحالات البوت'], ['↩️ رجوع للوحة الأدمن']]
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
    admin_quick = State()
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



# ---------------------------------------------------------------- undo of the V45 "remove two zeros" conversion
MIGRATION_REPORT=None
SETTING_AMOUNT_KEYS=('free_withdraw_max','sham_max_withdraw','loyalty_gift_amount','loyalty_balance_amount','referral_monthly_cap','referral_total_cap')

def prepare_revert_backup():
    """If this DB was converted by V45 (currency_scale='new'), keep a full copy before restoring the zeros."""
    if not DB.exists(): return None
    con=sqlite3.connect(DB,timeout=30)
    try:
        if not con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'").fetchone(): return None
        r=con.execute("SELECT value FROM settings WHERE key='currency_scale'").fetchone()
        if not r or r[0]!='new': return None
        dest=DB.with_name(DB.name+f'.pre_revert_{int(time.time())}.bak')
        dst=sqlite3.connect(dest)
        try: con.backup(dst)
        finally: dst.close()
        return str(dest)
    finally: con.close()

def revert_redenomination(c,backup_path=None):
    """One-time: multiply every money amount by 100 again if (and only if) V45 had divided them."""
    r=c.execute("SELECT value FROM settings WHERE key='currency_scale'").fetchone()
    if not r or r[0]!='new': return None
    one=lambda sql: c.execute(sql).fetchone()[0] or 0
    tabs={x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    rep=dict(backup=backup_path,users_with_balance=one('SELECT COUNT(*) FROM users WHERE bot_balance<>0'),balances_before=one('SELECT COALESCE(SUM(bot_balance),0) FROM users'))
    for tb,cols in (('users',('bot_balance',)),('bot_ledger',('delta','balance_after')),('deposits',('amount',)),
                    ('withdrawals',('amount_syp','fee_syp','payout_syp','balance_before','balance_after')),('gift_codes',('amount',)),
                    ('referral_finance',('amount',)),('referral_commissions',('amount',)),('referral_paid_deposits',('amount',))):
        if tb in tabs:
            for col in cols: c.execute(f'UPDATE {tb} SET {col}={col}*100 WHERE {col} IS NOT NULL')
    for row in c.execute("SELECT id,method,payout_amount,exchange_rate FROM withdrawals").fetchall():
        if row['method']=='sham_usd':
            if row['exchange_rate'] is not None: c.execute('UPDATE withdrawals SET exchange_rate=? WHERE id=?',(round(float(row['exchange_rate'])*100,2),row['id']))
        else:
            try: c.execute('UPDATE withdrawals SET payout_amount=? WHERE id=?',(str(int(float(row['payout_amount']))*100),row['id']))
            except (TypeError,ValueError): pass
    for key in SETTING_AMOUNT_KEYS:
        x=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        if x:
            try: c.execute('UPDATE settings SET value=? WHERE key=?',(str(int(round(float(x['value'])*100))),key))
            except (TypeError,ValueError): pass
    x=c.execute("SELECT value FROM settings WHERE key='dollar_rate'").fetchone()
    if x:
        try: c.execute("UPDATE settings SET value=? WHERE key='dollar_rate'",(f"{float(str(x['value']).replace(',',''))*100:g}",))
        except (TypeError,ValueError): pass
    rep['balances_after']=one('SELECT COALESCE(SUM(bot_balance),0) FROM users')
    c.execute("UPDATE settings SET value='old' WHERE key='currency_scale'")
    c.execute('INSERT INTO audit(actor,action,details) VALUES(?,?,?)',(0,'currency_revert',str(rep)))
    return rep

def init():
    global MIGRATION_REPORT
    backup_path=prepare_revert_backup()
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
        CREATE TABLE IF NOT EXISTS wheel_spins(deposit_id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,awarded_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS wheel_plays(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,outcome TEXT NOT NULL,played_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS wheel_bonuses(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,percent INTEGER NOT NULL DEFAULT 5,expires_at INTEGER NOT NULL,used_deposit_id INTEGER UNIQUE);
        CREATE TABLE IF NOT EXISTS referral_paid_deposits(deposit_id INTEGER PRIMARY KEY, referrer_id INTEGER NOT NULL, amount INTEGER NOT NULL, paid_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS cashback_claims(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,deposit_id INTEGER NOT NULL UNIQUE,deposit_amount INTEGER NOT NULL,cashback_amount INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'armed',created_at TEXT DEFAULT CURRENT_TIMESTAMP,requested_at TEXT,reviewed_by INTEGER,reviewed_at TEXT);
        CREATE TABLE IF NOT EXISTS refund_requests(id INTEGER PRIMARY KEY AUTOINCREMENT,withdrawal_id INTEGER NOT NULL UNIQUE,user_id INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',requested_at TEXT DEFAULT CURRENT_TIMESTAMP,reviewed_by INTEGER,reviewed_at TEXT);
        
        ''')
        if 'free_withdrawals' not in {r[1] for r in c.execute('PRAGMA table_info(users)')}:
            c.execute('ALTER TABLE users ADD COLUMN free_withdrawals INTEGER NOT NULL DEFAULT 0')
        if 'kind' not in {r[1] for r in c.execute('PRAGMA table_info(wheel_bonuses)')}:
            c.execute("ALTER TABLE wheel_bonuses ADD COLUMN kind TEXT NOT NULL DEFAULT 'bonus'")
        withdrawal_cols={r[1] for r in c.execute('PRAGMA table_info(withdrawals)')}
        for col in ('balance_before','balance_after'):
            if col not in withdrawal_cols:
                c.execute(f'ALTER TABLE withdrawals ADD COLUMN {col} INTEGER')
        if 'used_free' not in withdrawal_cols:
            c.execute('ALTER TABLE withdrawals ADD COLUMN used_free INTEGER NOT NULL DEFAULT 0')
        cols={r[1] for r in c.execute('PRAGMA table_info(users)')}
        if 'bot_balance' not in cols: c.execute('ALTER TABLE users ADD COLUMN bot_balance INTEGER NOT NULL DEFAULT 0')
        MIGRATION_REPORT=revert_redenomination(c,backup_path)  # restores the zeros if V45 had removed them
        c.execute("INSERT OR IGNORE INTO settings VALUES ('enabled','1')")
        c.execute("INSERT OR IGNORE INTO settings VALUES ('bonuses','لا توجد عروض حالية')")
        # Apply this requested default once, without overwriting later admin edits.
        if not c.execute("SELECT 1 FROM settings WHERE key='bonuses_v20_applied'").fetchone():
            c.execute("INSERT INTO settings(key,value) VALUES('bonuses','لا توجد عروض حالية') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
            c.execute("INSERT INTO settings(key,value) VALUES('bonuses_v20_applied','1')")
        for key,value in [('dollar_rate','14250'),('cashback','10'),('weekly_cashback','10'),('referral_reward','0'),('referral_percent','5'),('withdraw_fee_percent','10'),('free_withdraw_max','10000'),('sham_max_withdraw','50000'),('loyalty_cost_spin','60'),('loyalty_cost_gift','75'),('loyalty_gift_amount','200'),('loyalty_cost_balance','150'),('loyalty_balance_amount','350'),('loyalty_cost_nofee','300'),('referral_next_distribution',str(int(datetime(2026,10,28,19,0,tzinfo=timezone(timedelta(hours=3))).timestamp()))),('referral_last_distribution',str(int(datetime(2026,10,18,19,0,tzinfo=timezone(timedelta(hours=3))).timestamp()))),('referral_min_active','3'),('referral_min_transfers','3'),('referral_min_days','3'),('referral_maturity_days','7'),('referral_monthly_cap','5000'),('referral_total_cap','500000'),('terms','يرجى الالتزام بشروط استخدام البوت.'),('tutorials','لا توجد شروحات منشورة حالياً.'),('vpn_url',''),('apk_url',''),('games_url',''),('direct_url',''),('contact_url',''),('free_spin','غير متاح حالياً.'),('current_prize','لا توجد جائزة حالية.'),('sham_codes',''),('syriatel_codes','')]:
            c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(key,value))

        if not c.execute("SELECT 1 FROM settings WHERE key='prize_amounts_v47'").fetchone():
            for k,old,new in (('loyalty_gift_amount','20000','200'),('loyalty_balance_amount','35000','350'),('referral_monthly_cap','500000','5000'),('referral_total_cap','5000000','500000')):
                c.execute('UPDATE settings SET value=? WHERE key=? AND value=?',(new,k,old))
            c.execute("INSERT INTO settings(key,value) VALUES('prize_amounts_v47','1')")
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
# Button ids are frozen so menus that users/admins already have in their chats keep pointing at the same actions.
LEGACY_BUTTON_ORDER = [
 "🟥 Ichancy",
 "💸 شحن رصيد البوت",
 "💰 سحب رصيد البوت",
 "💸 نظام الإحالات",
 "🎟️ إهداء رصيد",
 "🎁 كود هدية",
 "📝 رسالة للأدمن",
 "💌 تواصل معنا",
 "✅ السجل",
 "⚠️ الشروحات",
 "↗️ Vpn لتشغيل كامل أقسام الموقع",
 "↗️ ichancy apk",
 "💜 الشروط والأحكام",
 "💵 اللفة المجانية",
 "🎁 البونصات والعروض الحالية",
 "🎰 ألعاب Ichancy",
 "⭐ دخول مباشر للألعاب",
 "🌟 نقاط الولاء",
 "👥 المستخدمين",
 "🎁 العروض والبونصات",
 "🌟 إدارة نقاط الولاء",
 "📢 الإذاعة",
 "⚙️ إعدادات البوت",
 "📊 التقارير",
 "🎟️ الأكواد",
 "💰 الإحالات",
 "🏠 القائمة الرئيسية",
 "🔎 البحث عن مستخدم",
 "📜 سجل مستخدم",
 "➕ إضافة رصيد",
 "➖ خصم رصيد",
 "🚫 حظر مستخدم",
 "🔓 فك حظر مستخدم",
 "↩️ رجوع للوحة الأدمن",
 "📝 تعديل نص العروض والبونصات",
 "➕ منح نقاط ولاء",
 "➖ خصم نقاط ولاء",
 "🎁 تعديل جوائز نقاط الولاء",
 "⚙️ حالة البوت (تشغيل/إيقاف)",
 "⚙️ تعديل سعر الدولار",
 "🔥 حرق رقم عملية",
 "📝 إدارة المحتوى والروابط",
 "📊 تقرير",
 "🎟️ إضافة كود",
 "💳 تعديل أكواد شام كاش",
 "💳 تعديل أكواد سيريتل كاش",
 "⚙️ إعدادات نظام الإحالات",
 "📋 سجل إحالات البوت",
 "🎁 استبدال نقاط",
 "🎁 إنشاء جائزة ولاء",
 "👮 لوحة تحكم الإدارة"
]
BUTTON_IDS = {label: f'btn_{i}' for i, label in enumerate(LEGACY_BUTTON_ORDER)}
BUTTON_IDS[REFUND_LABEL] = 'btn_refund_wd'
BUTTON_IDS[DIST_LABEL] = 'btn_ref_dist'
BUTTON_IDS[PENDING_LABEL] = 'btn_pending_req'
BUTTON_IDS[FEES_LABEL] = 'btn_fees_cfg'
for _g in ROWS + ADMIN_ROWS + USER_ADMIN_ROWS + BONUS_ADMIN_ROWS + LOYALTY_ADMIN_ROWS + SETTINGS_ADMIN_ROWS + REPORT_ADMIN_ROWS + CODE_ADMIN_ROWS + REFERRAL_ADMIN_ROWS:
    for _l in _g:
        BUTTON_IDS.setdefault(_l, f'btn_n{len(BUTTON_IDS)}')
ID_BUTTONS = {v: k for k, v in BUTTON_IDS.items()}

STYLE_BY_LABEL = {'🟥 Ichancy': 'primary'}  # Bot API button colours: primary=blue, success=green, danger=red

def sbtn(text, callback_data, style=None):
    """Inline button with optional Telegram colour. `style` is sent as an extra field, so it also works on
    aiogram versions without a native `style` attribute (older servers/clients simply ignore it)."""
    kw = {'text': text, 'callback_data': callback_data}
    if style: kw['style'] = style
    return InlineKeyboardButton(**kw)

def keyboard(rows):
    return InlineKeyboardMarkup(inline_keyboard=[
        [sbtn(label, BUTTON_IDS[label], STYLE_BY_LABEL.get(label)) for label in group]
        for group in rows
    ])


# ---------------------------------------------------------------- admin panel helpers
BAR='━━━━━━━━━━━━━━━━'

def admin_counts():
    with db() as c:
        q=lambda sql: c.execute(sql).fetchone()[0]
        return dict(users=q('SELECT COUNT(*) FROM users'),banned=q('SELECT COUNT(*) FROM users WHERE banned=1'),
                    wd=q("SELECT COUNT(*) FROM withdrawals WHERE status='pending'"),dep=q("SELECT COUNT(*) FROM deposits WHERE status='pending'"),
                    ref=q("SELECT COUNT(*) FROM refund_requests WHERE status='pending'"),cbk=q("SELECT COUNT(*) FROM cashback_claims WHERE status IN ('armed','requested')"),claims=q("SELECT COUNT(*) FROM claims WHERE status='pending'"))

def bot_state_line():
    return '🟢 البوت يعمل' if setting('enabled')=='1' else '⏸️ البوت موقوف للمستخدمين (الأدمن يعمل)'

def admin_panel_text():
    k=admin_counts()
    return (f'👮 لوحة تحكم الإدارة — {NAME}\n{BAR}\n{bot_state_line()}\n👥 المستخدمون: {k["users"]:,}   🚫 محظورون: {k["banned"]:,}\n\n'
            f'📋 بانتظار المعالجة:\n• 💸 طلبات سحب: {k["wd"]}\n• 💳 طلبات إيداع: {k["dep"]}\n• ↩️ طلبات استرداد سحب: {k["ref"]}\n• 💸 كاش باك مفعّل (بانتظار نهاية الأسبوع): {k["cbk"]}\n\n'
            f'📤 توزيع الإحالات القادم: {fmt_local(next_distribution_ts())} (توقيت دمشق)'+(' ⏰ حان الموعد' if next_distribution_ts()<=time.time() else '')+f'\n{BAR}\nاختر القسم المطلوب 👇')

def admin_menu_text(label):
    if label=='🌟 إدارة نقاط الولاء':
        return ('🌟 إدارة نقاط الولاء\n'+BAR+'\n• ➕ منح نقاط ولاء: إضافة نقاط لمستخدم\n• ➖ خصم نقاط ولاء: سحب نقاط من مستخدم\n'
                '• 🎁 تعديل جوائز نقاط الولاء: تكلفة وقيمة الجوائز الأربع (لفة، كود هدية، رصيد، سحب بدون عمولة)\n\n'
                f'التكلفة الحالية: لفة {setting("loyalty_cost_spin")} | كود {setting("loyalty_cost_gift")} | رصيد {setting("loyalty_cost_balance")} | سحب مجاني {setting("loyalty_cost_nofee")} نقطة')
    if label=='⚙️ إعدادات البوت':
        return ('⚙️ إعدادات البوت\n'+BAR+f'\n• الحالة الحالية: {bot_state_line()}\n• سعر الدولار (شام كاش): {setting("dollar_rate")} ل.س\n'
                f'• عمولة السحب: {fee_percent():g}% | سحب بدون عمولة حتى {int_setting("free_withdraw_max",10000):,} | حد شام كاش {sham_max():,}\n\n'
                '• ⚙️ حالة البوت: تشغيل/إيقاف للمستخدمين\n• 💸 عمولة وحدود السحب: النسبة والحدود\n• ⚙️ تعديل سعر الدولار\n• 🔥 حرق رقم عملية: منع إعادة استخدامه\n• 📝 إدارة المحتوى والروابط: الشروط، الشروحات، الروابط')
    if label=='📊 التقارير':
        return '📊 التقارير\n'+BAR+'\n• 📊 تقرير: ملخص شامل للمستخدمين والإيداعات والسحوبات والعجلة والإحالات'
    if label=='🎟️ الأكواد':
        return '🎟️ إدارة الأكواد\n'+BAR+'\n• 🎟️ إضافة كود: كود هدية برصيد داخلي\n• 💳 تعديل أكواد شام كاش / سيريتل كاش: أرقام استقبال الإيداع'
    if label=='💰 الإحالات':
        return ('💰 إدارة الإحالات\n'+BAR+'\n• 📤 توزيع الإحالات: معاينة ثم صرف الأرباح بعد تأكيدك\n• ⚙️ إعدادات نظام الإحالات: النسبة والحد الأدنى وغيرها\n• 📋 سجل إحالات البوت: أكثر المُحيلين\n\n'
                f'النسبة: {setting("referral_percent")}% | الحد الأدنى للإحالات النشطة: {setting("referral_min_active")}\nالموعد القادم: {fmt_local(next_distribution_ts())}')
    return None

def pending_text():
    with db() as c:
        wd=c.execute("SELECT id,user_id,method,amount_syp FROM withdrawals WHERE status='pending' ORDER BY id LIMIT 8").fetchall()
        dep=c.execute("SELECT id,user_id,method,amount FROM deposits WHERE status='pending' ORDER BY id LIMIT 8").fetchall()
        rf=c.execute("SELECT r.id,r.withdrawal_id,r.user_id FROM refund_requests r WHERE r.status='pending' ORDER BY r.id LIMIT 8").fetchall()
    k=admin_counts()
    def block(title,n,rows,fmt): return f'{title} ({n})\n'+('\n'.join(fmt(r) for r in rows) if rows else '• لا يوجد')+('\n• ... والمزيد' if n>len(rows) else '')
    return ('📋 الطلبات المعلّقة\n'+BAR+'\n'+
            block('💸 سحب',k['wd'],wd,lambda r:f"• #{r['id']} | {r['user_id']} | {WITHDRAW_METHOD_NAMES.get(r['method'],r['method'])} | {r['amount_syp']:,} ل.س")+'\n\n'+
            block('💳 إيداع',k['dep'],dep,lambda r:f"• #{r['id']} | {r['user_id']} | {r['method']} | {r['amount']:,} ل.س")+'\n\n'+
            block('↩️ استرداد سحب',k['ref'],rf,lambda r:f"• طلب #{r['id']} للسحب #{r['withdrawal_id']} | {r['user_id']}")+
            f'\n{BAR}\nتُعالَج الطلبات من أزرار قنواتها (سحب / إيداع / استرداد). الكاش باك وجوائز الولاء تُضاف تلقائياً.')

def report_text():
    with db() as c:
        q=lambda sql,*a: c.execute(sql,a).fetchone()
        u=q("SELECT COUNT(*),SUM(banned=1),SUM(joined>=datetime('now','-1 day')),COALESCE(SUM(bot_balance),0),COALESCE(SUM(points),0) FROM users")
        dp=q("SELECT SUM(status='approved'),COALESCE(SUM(CASE WHEN status='approved' THEN amount END),0),SUM(status='pending'),SUM(status='approved' AND reviewed_at>=datetime('now','-1 day')),COALESCE(SUM(CASE WHEN status='approved' AND reviewed_at>=datetime('now','-1 day') THEN amount END),0) FROM deposits")
        wd=q("SELECT SUM(status='approved'),COALESCE(SUM(CASE WHEN status='approved' THEN amount_syp END),0),SUM(status='pending'),COALESCE(SUM(CASE WHEN status='pending' THEN amount_syp END),0),SUM(status='rejected'),SUM(status='refunded'),COALESCE(SUM(CASE WHEN status='approved' THEN fee_syp END),0) FROM withdrawals")
        wh=q("SELECT (SELECT COUNT(*) FROM wheel_spins),COUNT(*),SUM(outcome='hardluck'),SUM(outcome='bonus'),SUM(outcome='cashback') FROM wheel_plays")
        rf=q("SELECT COUNT(DISTINCT referrer) FROM users WHERE referrer IS NOT NULL"),q("SELECT COUNT(*) FROM users WHERE referrer IS NOT NULL"),q("SELECT COALESCE(SUM(amount),0) FROM referral_commissions WHERE status='paid'")
        lx=q("SELECT COUNT(*) FROM audit WHERE action='loyalty_prize_exchange'")
        cb=q("SELECT SUM(status='armed'),SUM(status='requested'),SUM(status='paid'),COALESCE(SUM(CASE WHEN status='paid' THEN cashback_amount END),0),SUM(status='void') FROM cashback_claims")
    n=lambda v:int(v or 0)
    return (f'📊 تقرير شامل — {NAME}\n{BAR}\n'
            f'👥 المستخدمون\n• الإجمالي: {n(u[0]):,} | محظور: {n(u[1])} | جدد آخر 24س: {n(u[2])}\n• مجموع أرصدة البوت الداخلية: {n(u[3]):,} ل.س\n• مجموع نقاط الولاء: {n(u[4]):,}\n\n'
            f'💳 الإيداعات\n• المعتمدة: {n(dp[0])} بإجمالي {n(dp[1]):,} ل.س | معلّقة: {n(dp[2])}\n• آخر 24 ساعة: {n(dp[3])} بإجمالي {n(dp[4]):,} ل.س\n\n'
            f'💸 السحوبات\n• المعتمدة: {n(wd[0])} بإجمالي {n(wd[1]):,} ل.س | العمولات المحصّلة: {n(wd[6]):,} ل.س\n• معلّقة: {n(wd[2])} ({n(wd[3]):,} ل.س) | مرفوضة: {n(wd[4])} | مستردة: {n(wd[5])}\n\n'
            f'🎡 العجلة\n• لفات ممنوحة: {n(wh[0])} | لفات مُنفّذة: {n(wh[1])}\n• HARDLUCK: {n(wh[2])} | بونص 5%: {n(wh[3])} | كاش باك 5%: {n(wh[4])}\n\n'
            f'💰 الإحالات\n• وكلاء لديهم إحالات: {n(rf[0][0])} | إجمالي الإحالات: {n(rf[1][0])}\n• أرباح موزّعة: {n(rf[2][0]):,} ل.س\n\n'
            f'💸 الكاش باك (تلقائي)\n• مفعّل بانتظار الأسبوع: {n(cb[0])+n(cb[1])} | مصروف: {n(cb[2])} ({n(cb[3]):,} ل.س) | ملغى (حصل سحب): {n(cb[4])}\n\n🌟 الولاء\n• عمليات استبدال الجوائز: {n(lx[0])}\n{BAR}\n🕒 {datetime.now(DAMASCUS).strftime("%Y-%m-%d %H:%M")} (توقيت دمشق)')

CONFIG_NAMES={'withdraw_fee_percent':('عمولة السحب العادية (%)','أرسل النسبة من 0 إلى 100 (مثال: 10 أو 7.5).'),
              'free_withdraw_max':('حد «سحب بدون عمولة» (ل.س)','أرسل أعلى مبلغ يُسمح فيه بالسحب المجاني (مثال: 10000). المبالغ الأكبر تُحسب بالعمولة العادية.'),
              'sham_max_withdraw':('الحد الأقصى لسحب شام كاش (ل.س)','أرسل الحد الأقصى لطلب سحب شام كاش (مثال: 50000).')}

def fees_text():
    return ('💸 عمولة وحدود السحب\n'+BAR+f'\n• عمولة السحب العادية: {fee_percent():g}%\n• «سحب بدون عمولة» (جائزة الولاء): للمبالغ حتى {int_setting("free_withdraw_max",10000):,} ل.س فقط\n'
            f'• الحد الأقصى لسحب شام كاش: {sham_max():,} ل.س (للمبالغ الأكبر يتواصل المستخدم مع {SUPPORT_USERNAME})\n{BAR}\nاضغط على القيمة التي تريد تعديلها 👇')

def fees_keyboard():
    rows=[[InlineKeyboardButton(text=f'✏️ {CONFIG_NAMES[k][0]}',callback_data='ac:cfg:'+k)] for k in ('withdraw_fee_percent','free_withdraw_max','sham_max_withdraw')]
    rows.append([InlineKeyboardButton(text='↩️ رجوع للوحة الأدمن',callback_data=BUTTON_IDS['↩️ رجوع للوحة الأدمن'])])
    return InlineKeyboardMarkup(inline_keyboard=rows)

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
    with db() as c:
        active=c.execute('SELECT expires_at,kind FROM wheel_bonuses WHERE user_id=? AND used_deposit_id IS NULL AND expires_at>? ORDER BY expires_at ASC LIMIT 1',(m.chat.id,int(time.time()))).fetchone()
    if not active: bonus_note=''
    elif active['kind']=='cashback': bonus_note='\n💸 لديك كاش باك 5%: يتفعّل على إيداعك القادم، وإذا لم تسحب خلال أسبوع يُضاف لك التعويض تلقائياً (لمرة واحدة)'
    else: bonus_note=f'\n🎁 لديك بونص إيداع 5% متاح حتى {datetime.fromtimestamp(active["expires_at"],timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}'
    await m.answer('💰 اختر طريقة شحن الرصيد الداخلي (تحقق تلقائي):'+bonus_note,reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🟢 شام كاش - دولار',callback_data='dep:sham_usd'),InlineKeyboardButton(text='🟢 شام كاش - سوري',callback_data='dep:sham')],
        [InlineKeyboardButton(text='📱 سيريتل كاش',callback_data='dep:syriatel')],
        [InlineKeyboardButton(text='↩️ الرئيسية',callback_data=BUTTON_IDS['🏠 القائمة الرئيسية'])]]))

def syriatel_numbers():
    nums=[x for x in re.split(r'[,\s،|]+',SYRIATEL_ACCOUNT) if x]
    return nums or [SYRIATEL_ACCOUNT]

async def deposit_instructions(m,method,uid):
    from html import escape
    if method in ('sham','sham_usd'):
        msg=('💳 شحن تلقائي عبر شام كاش\n\n'
             'حوّل إلى العنوان التالي:\n'
             f'<code>{escape(SHAM_ACCOUNT)}</code>\n\n'
             '⚠️ لا تُخفِ بيانات التحويل.\n'
             'بعد التحويل، أرسل رقم العملية فقط للتحقق التلقائي.')
        if QR.exists():
            await m.answer_photo(FSInputFile(QR),caption='📸 رمز ShamCash للدفع')
    else:
        nums='\n'.join(f'<code>{escape(n)}</code>' for n in syriatel_numbers())
        msg=('💳 شحن تلقائي عبر سيريتل كاش\n\n'
             'حوّل إلى أحد الأرقام التالية:\n'
             f'{nums}\n\n'
             'بعد التحويل، أرسل رقم العملية فقط للتحقق التلقائي.')
    # No copy/transfer-completed buttons; FSM starts immediately.
    await m.answer(msg,parse_mode='HTML')

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

def int_setting(key,default):
    try: return int(float(setting(key) or default))
    except (TypeError,ValueError): return default

def fee_percent():
    try:
        v=float(setting('withdraw_fee_percent') or 10)
        return v if 0<=v<=100 else 10.0
    except (TypeError,ValueError): return 10.0

def calc_fee(syp,pct): return (int(syp)*int(round(pct*100))+9999)//10000

def sham_max(): return int_setting('sham_max_withdraw',SHAM_MAX_WITHDRAW)

def withdrawal_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🟥 سيرياتيل كاش',callback_data='wd:syriatel')],
        [InlineKeyboardButton(text='💠 شام كاش',callback_data='wd:sham_menu')],
        [InlineKeyboardButton(text='🟢 USDT',callback_data='wd:unavailable')],
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
    bounds='⬇️ الحد الأدنى للسحب: 400\n⬆️ الحد الأقصى للسحب: 50000\n\n' if method=='syriatel' else f'⬆️ الحد الأقصى للسحب: {sham_max()} ليرة سورية جديدة\n📩 للمبالغ الكبيرة يرجى مراسلة الدعم {SUPPORT_USERNAME}\n\n'
    await state.set_state(Input.withdrawal_amount)
    await state.update_data(withdrawal_method=method)
    await q.message.answer(f'{title}\n\n💱 العملة: {currency}\n\n{bounds}🏷 رسوم السحب: {fee_percent():g}%\n\n💰 رصيدك الحالي: {display_balance}\n\nادخل المبلغ الذي تريد سحبه ⏳'+('\n(المبلغ بالدولار، وسعر الصرف المعتمد: '+str(rate)+' SYP لكل USD)' if method=='sham_usd' else ''))

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
    await send_admin_panel(m)

# The admin panel is a normal (reply) keyboard shown under the message box, laid out like the reference screenshots.
ADMIN_REPLY_ROWS = [
    ['المستخدمين'],
    ['🔎 البحث عن مستخدم'],
    ['تقرير'],
    ['اضافة كود'],
    ['📜 سجل مستخدم'],
    ['💰 توزيع أرباح الإحالات'],
    ['➕ إضافة رصيد', '➖ خصم رصيد'],
    ['تعديل نص البونصات و العروض الحالية'],
    ['اضافة او حذف البونص'],
    ['الإذاعة'],
    ['تعديل اكواد سيرياتيل كاش', 'تعديل اكواد شام كاش'],
    ['⚙️ حالة البوت (تشغيل/إيقاف)'],
    ['⚙️ تعديل سعر الدولار'],
    ['🔥 حرق رقم عملية'],
    ['الكاش باك الأسبوعي 10%'],
    ['🎁 إدارة الجائزة الحالية'],
    ['🚫 حظر مستخدم', '🔓 فك حظر مستخدم'],
    ['القائمة الرئيسية'],
]
ADMIN_REPLY_ALL = {t for row in ADMIN_REPLY_ROWS for t in row}

def admin_reply_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t) for t in row] for row in ADMIN_REPLY_ROWS],
                               resize_keyboard=True,input_field_placeholder='👮 لوحة تحكم الإدارة')

async def send_admin_panel(m):
    await m.answer(admin_panel_text(),reply_markup=admin_reply_keyboard())

def admin_extras_keyboard():
    # tools added after the reference design stay reachable from the report message
    labels=[[PENDING_LABEL],[FEES_LABEL],['🌟 إدارة نقاط الولاء'],['⚙️ إعدادات نظام الإحالات','📋 سجل إحالات البوت'],['📝 إدارة المحتوى والروابط']]
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=l,callback_data=BUTTON_IDS[l]) for l in row] for row in labels])

# label -> (action understood by admin_action) for the buttons that map 1:1 to an existing admin action
ADMIN_REPLY_ACTIONS = {
    'اضافة كود':'🎟️ إضافة كود','📜 سجل مستخدم':'📜 سجل مستخدم',
    'اضافة او حذف البونص':'🎁 إضافة أو حذف البونص','تعديل اكواد شام كاش':'💳 تعديل أكواد شام كاش','تعديل اكواد سيرياتيل كاش':'💳 تعديل أكواد سيريتل كاش',
    '⚙️ تعديل سعر الدولار':'⚙️ تعديل سعر الدولار','🔥 حرق رقم عملية':'🔥 حرق رقم عملية','الكاش باك الأسبوعي 10%':'💸 الكاش باك الأسبوعي 10%','🎁 إدارة الجائزة الحالية':'🎁 إدارة الجائزة الحالية'}

@router.message(F.text.in_(ADMIN_REPLY_ALL), F.from_user.id.in_(ADMIN_IDS))
async def admin_reply_dispatch(m:Message,state:FSMContext):
    t=m.text
    await state.clear()
    if t=='المستخدمين':
        msg=await m.answer('👥 جارٍ تحميل المستخدمين...'); return await show_user_list(msg,0)
    if t=='🔎 البحث عن مستخدم': return await admin_search_start(m,state)
    if t=='تقرير': return await m.answer(report_text(),reply_markup=admin_extras_keyboard())
    if t=='💰 توزيع أرباح الإحالات': return await referral_distribution_preview(m)
    if t in ('➕ إضافة رصيد','➖ خصم رصيد'):
        await state.set_state(Input.admin_quick); await state.update_data(qa='credit' if t.startswith('➕') else 'debit')
        return await m.answer(f"{'➕ إضافة رصيد' if t.startswith('➕') else '➖ خصم رصيد'} (رصيد البوت الداخلي)\nأرسل آيدي المستخدم ثم المبلغ في رسالة واحدة:\n<code>123456789 5000</code>\nللإلغاء اضغط أي زر من اللوحة أو أرسل /cancel",parse_mode='HTML')
    if t=='تعديل نص البونصات و العروض الحالية': return await bonus_start(m,state)
    if t=='الإذاعة': return await broadcast_start(m,state)
    if t=='⚙️ حالة البوت (تشغيل/إيقاف)': return await toggle(m)
    if t in ('🚫 حظر مستخدم','🔓 فك حظر مستخدم'): return await ban_start(m,state)
    if t=='القائمة الرئيسية':
        await m.answer('🏠 تم الخروج من لوحة الإدارة.',reply_markup=ReplyKeyboardRemove())
        return await home(m)
    if t in ADMIN_REPLY_ACTIONS: return await admin_action(m,state,m.from_user,ADMIN_REPLY_ACTIONS[t])

@router.message(Input.admin_quick)
async def admin_quick_finish(m:Message,state:FSMContext):
    import re, unicodedata
    if not admin(m.from_user): return
    raw=''.join(str(unicodedata.decimal(ch)) if ch.isdecimal() else ch for ch in (m.text or '')).replace('٬','').replace(',','')
    mt=re.fullmatch(r'\s*(\d+)\s+(\d+)\s*',raw)
    if not mt: return await m.answer('❌ الصيغة غير صحيحة. أرسل الآيدي ثم المبلغ مفصولين بمسافة، مثال:\n123456789 5000')
    uid,amount=int(mt.group(1)),int(mt.group(2))
    data=await state.get_data(); credit=data.get('qa')=='credit'
    if not 0<amount<=1000000000: return await m.answer('❌ المبلغ غير صحيح.')
    err=None
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        if not c.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone(): err='❌ هذا الآيدي غير مسجل في البوت.'
        else:
            try: new=add_local_balance(c,uid,amount if credit else -amount,m.from_user.id)
            except ValueError as e: err=f'❌ {e}'
    if err: return await m.answer(err)
    audit(m.from_user.id,'admin_balance_credit' if credit else 'admin_balance_debit',f'{uid}:{amount}')
    await state.clear()
    await m.answer(f"✅ تم {'إضافة' if credit else 'خصم'} {amount:,} ل.س {'إلى' if credit else 'من'} المستخدم {uid}.\n💰 رصيده الآن: {new:,} ل.س (داخل البوت فقط)")
    await notify_user(m.bot,uid,f"{'💰 تمت إضافة' if credit else '➖ تم خصم'} {amount:,} ل.س {'إلى رصيدك' if credit else 'من رصيدك'} الداخلي بواسطة الإدارة.\nرصيدك الآن: {new:,} ل.س")

@router.message(F.text == '🏠 القائمة الرئيسية')
async def go_home(m:Message,state:FSMContext):
    await state.clear()
    await home(m)

def loyalty_options():
    with db() as c:
        return c.execute('SELECT points,credit FROM loyalty_exchange_options WHERE active=1 ORDER BY points').fetchall()

def loyalty_prizes():
    def g(key,default):
        try: return int(float(setting(key) or default))
        except (TypeError,ValueError): return default
    gift=g('loyalty_gift_amount',200); bal=g('loyalty_balance_amount',350)
    return [dict(key='spin',emoji='🎡',title='لفة عجلة مجانية',cost=g('loyalty_cost_spin',60)),
            dict(key='gift',emoji='🎁',title=f'كود هدية ({gift:,})',cost=g('loyalty_cost_gift',75),amount=gift),
            dict(key='balance',emoji='💰',title=f'رصيد بالبوت ({bal:,})',cost=g('loyalty_cost_balance',150),amount=bal),
            dict(key='nofee',emoji='💸',title='سحب بدون عمولة',cost=g('loyalty_cost_nofee',300))]

def loyalty_exchange_keyboard(points=0):
    rows=[[sbtn(f"{p['emoji']} {p['title']} - {p['cost']} نقطة"+(' 🔒' if points<p['cost'] else ''),f"loyalty:{p['key']}",None if points<p['cost'] else 'success')] for p in loyalty_prizes()]
    rows.append([InlineKeyboardButton(text='💝 عودة',callback_data=BUTTON_IDS['🏠 القائمة الرئيسية'])])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def loyalty_menu_text(points):
    return f'⭐ استبدال نقاط الولاء\n\nنقاطك الحالية: {points:,} نقطة\n\nاختر الجائزة المراد استبدالها:'

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
    if method in ('sham_syp','sham_usd') and syp>sham_max():
        return await m.answer(f'❌ الحد الأقصى للسحب عبر شام كاش هو {sham_max()} ليرة سورية جديدة.\n📩 للمبالغ الكبيرة يرجى مراسلة الدعم {SUPPORT_USERNAME}')
    if method=='syriatel' and not (400<=syp<=50000): return await m.answer('❌ المبلغ لازم يكون بين 400 و50000 ليرة سورية جديدة.')
    if syp>balance_of(m.from_user.id): return await m.answer('❌ رصيدك غير كافٍ. لا يمكنك سحب أكثر من رصيدك الداخلي.')
    with db() as c: fr=c.execute('SELECT free_withdrawals FROM users WHERE id=?',(m.from_user.id,)).fetchone()
    pct=fee_percent(); free_max=int_setting('free_withdraw_max',10000)
    has_token=bool(fr and fr['free_withdrawals']>0)
    has_free=has_token and syp<=free_max   # fee-free prize only for amounts up to the cap
    fee=0 if has_free else calc_fee(syp,pct)
    payout=syp-fee
    if payout<=0: return await m.answer('❌ المبلغ أقل من رسوم السحب.')
    out=f'{Decimal(payout)/rate:.2f}' if method=='sham_usd' else str(payout)
    await state.update_data(withdrawal_syp=syp,withdrawal_fee=fee,withdrawal_payout=payout,withdrawal_out=out,withdrawal_rate=rate,withdrawal_free=has_free)
    if has_free: await m.answer('💸 سيتم استخدام «سحب بدون عمولة» من جوائزك لهذا الطلب (بدون رسوم).')
    elif has_token: await m.answer(f'ℹ️ «سحب بدون عمولة» متاح للمبالغ حتى {free_max:,} ليرة سورية جديدة فقط. هذا الطلب أكبر من ذلك، لذلك سيُحسب بالعمولة العادية ({pct:g}%) وتبقى سحبتك المجانية محفوظة لطلب لاحق.')
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
            if data.get('withdrawal_free') and not c.execute('UPDATE users SET free_withdrawals=free_withdrawals-1 WHERE id=? AND free_withdrawals>0',(m.from_user.id,)).rowcount: raise LookupError('free')
            before=c.execute('SELECT bot_balance FROM users WHERE id=?',(m.from_user.id,)).fetchone()['bot_balance']
            new=add_local_balance(c,m.from_user.id,-data['withdrawal_syp'],m.from_user.id)
            cur=c.execute('INSERT INTO withdrawals(user_id,method,amount_syp,fee_syp,payout_syp,payout_currency,payout_amount,exchange_rate,recipient,balance_before,balance_after,used_free) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(
                m.from_user.id,method,data['withdrawal_syp'],data['withdrawal_fee'],data['withdrawal_payout'],'USD' if method=='sham_usd' else 'SYP',data['withdrawal_out'],float(data['withdrawal_rate']) if method=='sham_usd' and data.get('withdrawal_rate') is not None else None,recipient,before,new,1 if data.get('withdrawal_free') else 0))
            wid=cur.lastrowid
    except LookupError: return await m.answer('❌ تعذّر استخدام «سحب بدون عمولة» (استُهلك). أعد طلب السحب من البداية.')
    except ValueError: return await m.answer('❌ الرصيد غير كافٍ أو تغيّر أثناء الطلب. لم يتم تقديم السحب.')
    await m.answer(f'✅ تم تسجيل طلب السحب #{wid}\n\n💳 الطريقة: {WITHDRAW_METHOD_NAMES[method]}\n💰 المبلغ المحجوز: {data["withdrawal_syp"]:,} ليرة سورية جديدة\n🏷 رسوم السحب: {(str(data["withdrawal_fee"])+" ليرة") if data["withdrawal_fee"] else "بدون رسوم"}\n💸 الصافي المستحق: {data["withdrawal_out"]} {"USD" if method=="sham_usd" else "SYP"}\n🏦 الحساب/الرقم: {recipient}\n💰 رصيدك المتبقي: {new:,} ليرة سورية جديدة\n\n⏳ بانتظار مراجعة الإدارة والتحويل اليدوي.')
    await send_withdrawal_admin(m.bot,wid)

WITHDRAW_METHOD_NAMES={'syriatel':'سيرياتيل كاش','sham_syp':'شام كاش (SYP)','sham_usd':'شام كاش (USD)'}

def withdrawal_request_text(wid):
    from html import escape
    with db() as c:
        r=c.execute('SELECT * FROM withdrawals WHERE id=?',(wid,)).fetchone()
        if not r: return None
        u=c.execute('SELECT username,first_name FROM users WHERE id=?',(r['user_id'],)).fetchone()
        dep=c.execute("SELECT COUNT(*) n,COALESCE(SUM(amount),0) s FROM deposits WHERE user_id=? AND status='approved'",(r['user_id'],)).fetchone()
        wd=c.execute("SELECT COUNT(*) n,COALESCE(SUM(amount_syp),0) s FROM withdrawals WHERE user_id=? AND status='approved'",(r['user_id'],)).fetchone()
    name=escape((u['first_name'] if u and u['first_name'] else '-')); uname=('@'+escape(u['username'])) if u and u['username'] else '-'
    cur=r['payout_currency']; rate=f"\n• سعر الصرف: {r['exchange_rate']} SYP لكل USD" if r['method']=='sham_usd' and r['exchange_rate'] else ''
    fee='بدون رسوم (جائزة سحب مجاني)' if r['used_free'] else (f"{r['fee_syp']:,} ل.س" if r['fee_syp'] else 'بدون رسوم')
    return (f"📤 <b>طلب سحب جديد #{wid}</b>\n━━━━━━━━━━━━━━━━\n"
            f"👤 <b>المستخدم</b>\n• الاسم: {name}\n• اليوزر: {uname}\n• الآيدي: <code>{r['user_id']}</code>\n━━━━━━━━━━━━━━━━\n"
            f"💳 <b>تفاصيل الطلب</b>\n• طريقة السحب: {WITHDRAW_METHOD_NAMES.get(r['method'],r['method'])}\n"
            f"• المبلغ المخصوم من الرصيد: <b>{r['amount_syp']:,}</b> ل.س جديدة\n• رسوم السحب: {fee}\n"
            f"• الصافي المطلوب تحويله: <b>{r['payout_amount']} {cur}</b>{rate}\n"
            f"• الحساب/الرقم المستلم:\n<code>{escape(str(r['recipient']))}</code>\n━━━━━━━━━━━━━━━━\n"
            f"💰 <b>رصيد المستخدم</b>\n• قبل الطلب: {r['balance_before']:,} ل.س\n• بعد الحجز: {r['balance_after']:,} ل.س\n"
            f"📊 <b>سجل المستخدم</b>\n• إيداعات معتمدة: {dep['n']} (إجمالي {dep['s']:,} ل.س)\n• سحوبات معتمدة سابقة: {wd['n']} (إجمالي {wd['s']:,} ل.س)\n"
            f"🕒 وقت الطلب: {r['requested_at']}")

async def send_withdrawal_admin(bot,wid):
    msg=withdrawal_request_text(wid)
    if not msg: return False
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ تم التحويل — موافقة',callback_data=f'wreview:{wid}:approve'),InlineKeyboardButton(text='❌ رفض وإعادة الرصيد',callback_data=f'wreview:{wid}:reject')]])
    # Requests go ONLY to the withdrawal-requests channel (not to admins' private chats).
    if WITHDRAWAL_CHAT_ID:
        try:
            await bot.send_message(WITHDRAWAL_CHAT_ID,msg,parse_mode='HTML',reply_markup=kb); return True
        except Exception: logging.exception('Withdrawal request #%s failed to reach channel %s',wid,WITHDRAWAL_CHAT_ID)
    # Last resort only (channel missing / bot removed from it): do not lose the request.
    sent=False
    for dest in ADMIN_IDS:
        try: await bot.send_message(dest,'⚠️ تعذّر الإرسال لقناة طلبات السحب، هذا الطلب وصلك مباشرة:\n\n'+msg,parse_mode='HTML',reply_markup=kb); sent=True
        except Exception: logging.exception('Withdrawal fallback failed to admin %s',dest)
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
        if action=='reject':
            add_local_balance(c,r['user_id'],r['amount_syp'],q.from_user.id)
            if r['used_free']: c.execute('UPDATE users SET free_withdrawals=free_withdrawals+1 WHERE id=?',(r['user_id'],))  # give back the fee-free token
    await q.answer('تمت معالجة الطلب')
    try: await q.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    note=(f'✅ تمت الموافقة على طلب السحب #{wid}. ستصلك أرباحك بعد قليل.' if action=='approve' else f'❌ تم رفض طلب السحب #{wid} وإعادة كامل المبلغ المحجوز إلى رصيدك الداخلي.')
    try: await q.bot.send_message(r['user_id'],note)
    except Exception: logging.exception('Withdrawal notification to user failed')
    await q.message.answer(f'طلب السحب #{wid}: {action} بواسطة {q.from_user.id}')

async def refund_last_withdrawal(msg,bot,user):
    """User asks to refund their LAST withdrawal request; the request goes to REFUND_CHAT_ID for admin review."""
    uid=user.id
    with db() as c:
        w=c.execute('SELECT * FROM withdrawals WHERE user_id=? ORDER BY id DESC LIMIT 1',(uid,)).fetchone()
        rr=c.execute('SELECT * FROM refund_requests WHERE withdrawal_id=?',(w['id'],)).fetchone() if w else None
    if not w: return await msg.answer('ما عندك أي طلب سحب لاسترداده.')
    wid=w['id']
    if w['status']=='approved': return await msg.answer(f'طلب السحب #{wid} تمت الموافقة عليه وتحويله، لا يمكن استرداده.')
    if w['status'] in ('rejected','refunded'): return await msg.answer(f'طلب السحب #{wid} أُعيد مبلغه إلى رصيدك مسبقاً.')
    if rr:
        if rr['status']=='rejected': return await msg.answer(f'تم رفض طلب استرداد السحب #{wid} سابقاً.')
        return await msg.answer(f'طلب استرداد السحب #{wid} قيد المراجعة من الإدارة. لا حاجة لإرساله مرة ثانية.')
    with db() as c:
        cur=c.execute('INSERT OR IGNORE INTO refund_requests(withdrawal_id,user_id) VALUES(?,?)',(wid,uid))
        rid=cur.lastrowid if cur.rowcount else None
    if not rid: return await msg.answer(f'طلب استرداد السحب #{wid} قيد المراجعة من الإدارة.')
    uname=f'@{user.username}' if getattr(user,'username',None) else '-'
    text=(f'↩️ طلب استرداد سحب #{wid}\n🆔 المستخدم: {uid} ({uname})\n💳 الطريقة: {w["method"]}\n'
          f'💰 المبلغ المحجوز: {w["amount_syp"]:,} SYP\n💸 الصافي: {w["payout_amount"]} {w["payout_currency"]}\n'
          f'🏦 الوجهة: {w["recipient"]}\n🕒 وقت طلب السحب: {w["requested_at"]}\n'
          '⚠️ وافق فقط إذا لم يتم تحويل المبلغ فعلياً. الموافقة تُرجع المبلغ كاملاً لرصيد المستخدم وتلغي طلب السحب.')
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ موافقة وإعادة الرصيد',callback_data=f'rrefund:{rid}:approve'),InlineKeyboardButton(text='❌ رفض الاسترداد',callback_data=f'rrefund:{rid}:reject')]])
    sent=False
    targets=([REFUND_CHAT_ID] if REFUND_CHAT_ID else [])
    for dest in dict.fromkeys(targets):
        try: await bot.send_message(dest,text,reply_markup=kb);sent=True
        except Exception: logging.exception('Refund request failed to %s',dest)
    if not sent:  # channel unreachable (e.g. bot not admin there): fall back to admins so the request is not lost
        for dest in ADMIN_IDS:
            try: await bot.send_message(dest,text,reply_markup=kb);sent=True
            except Exception: logging.exception('Refund request failed to admin %s',dest)
    if not sent:
        with db() as c: c.execute('DELETE FROM refund_requests WHERE id=?',(rid,))
        return await msg.answer('❌ تعذّر إرسال طلب الاسترداد حالياً. حاول لاحقاً.')
    await msg.answer(f'✅ تم إرسال طلب استرداد السحب #{wid} إلى الإدارة للمراجعة. سيصلك إشعار بالنتيجة.')

@router.callback_query(F.data.startswith('rrefund:'))
async def review_refund(q:CallbackQuery):
    if not admin(q.from_user): return await q.answer('غير مصرح',show_alert=True)
    try: _,rid,action=q.data.split(':'); rid=int(rid)
    except (ValueError,AttributeError): return await q.answer('طلب غير صحيح',show_alert=True)
    if action not in ('approve','reject'): return await q.answer('إجراء غير صحيح',show_alert=True)
    outcome=None
    try:
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            rr=c.execute('SELECT * FROM refund_requests WHERE id=?',(rid,)).fetchone()
            if not rr or rr['status']!='pending': outcome='done'
            else:
                w=c.execute('SELECT * FROM withdrawals WHERE id=?',(rr['withdrawal_id'],)).fetchone()
                if action=='reject':
                    c.execute("UPDATE refund_requests SET status='rejected',reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(q.from_user.id,rid)); outcome='rejected'
                elif not w or w['status']!='pending':
                    c.execute("UPDATE refund_requests SET status='rejected',reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(q.from_user.id,rid)); outcome='blocked'
                else:
                    c.execute("UPDATE withdrawals SET status='refunded',reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'",(q.from_user.id,w['id']))
                    add_local_balance(c,w['user_id'],w['amount_syp'],q.from_user.id)
                    if w['used_free']: c.execute('UPDATE users SET free_withdrawals=free_withdrawals+1 WHERE id=?',(w['user_id'],))
                    c.execute("UPDATE refund_requests SET status='approved',reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(q.from_user.id,rid)); outcome='approved'
    except Exception:
        logging.exception('Refund review failed')
        return await q.answer('تعذّرت معالجة الطلب',show_alert=True)
    if outcome=='done': return await q.answer('الطلب عولج مسبقاً',show_alert=True)
    await q.answer('تمت معالجة الطلب')
    try: await q.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    wid=w['id'] if w else '?'
    notes={'approved':f'✅ تمت الموافقة على استرداد طلب السحب #{wid} وأُعيد {w["amount_syp"]:,} SYP إلى رصيدك الداخلي.' if w else '',
           'rejected':f'❌ تم رفض طلب استرداد السحب #{wid}. يبقى طلب السحب قيد المعالجة.',
           'blocked':f'❌ تعذّر استرداد السحب #{wid} لأنه عولج بالفعل.'}
    try: await q.bot.send_message(rr['user_id'],notes[outcome])
    except Exception: logging.exception('Refund notification to user failed')
    await q.message.answer(f'استرداد السحب #{wid}: {outcome} بواسطة {q.from_user.id}')

CASHBACK_PERCENT=5
CASHBACK_WEEK=7*86400

@router.callback_query(F.data.startswith('cbk:'))
async def cashback_click(q:CallbackQuery):
    # Old buttons from V45-V48 messages: compensation is automatic now.
    await q.answer('الكاش باك تلقائي: إذا لم تسحب خلال أسبوع من إيداعك يُضاف لك التعويض 5% تلقائياً.',show_alert=True)

async def settle_cashback(bot):
    """Automatic compensation (no approval): one week after the activating deposit, if the user made no withdrawal
    request in that week, add CASHBACK_PERCENT% of everything they deposited during the week; otherwise void it."""
    now=int(time.time()); paid=[]
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        claims=c.execute("SELECT *,CAST(strftime('%s',created_at) AS INTEGER) AS t0 FROM cashback_claims WHERE status IN ('armed','requested') AND CAST(strftime('%s',created_at) AS INTEGER)<=?",(now-CASHBACK_WEEK,)).fetchall()
        for cl in claims:
            t0,t1=cl['t0']-5,cl['t0']+CASHBACK_WEEK
            wd=c.execute("SELECT COUNT(*) FROM withdrawals WHERE user_id=? AND status NOT IN ('rejected','refunded') AND CAST(strftime('%s',requested_at) AS INTEGER) BETWEEN ? AND ?",(cl['user_id'],t0,t1)).fetchone()[0]
            if wd:
                c.execute("UPDATE cashback_claims SET status='void',reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(cl['id'],)); continue
            base=c.execute("SELECT COALESCE(SUM(amount),0) FROM deposits WHERE user_id=? AND status='approved' AND (id=? OR CAST(strftime('%s',reviewed_at) AS INTEGER) BETWEEN ? AND ?)",(cl['user_id'],cl['deposit_id'],t0,t1)).fetchone()[0]
            amount=base*CASHBACK_PERCENT//100
            if amount<=0:
                c.execute("UPDATE cashback_claims SET status='void',reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(cl['id'],)); continue
            add_local_balance(c,cl['user_id'],amount,0)
            c.execute("UPDATE cashback_claims SET status='paid',cashback_amount=?,deposit_amount=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(amount,base,cl['id']))
            paid.append((cl['user_id'],amount,base))
    for uid,amount,base in paid:
        try: await bot.send_message(uid,f'💸 تم إضافة كاش باك تلقائي: {amount:,} ل.س ({CASHBACK_PERCENT}% من إيداعاتك خلال الأسبوع: {base:,} ل.س) لأنك لم تقم بأي سحب خلال هذه الفترة.')
        except Exception: logging.exception('Cashback notification failed for %s',uid)
    return len(paid)

async def cashback_loop(bot):
    while True:
        try: await settle_cashback(bot)
        except Exception: logging.exception('Cashback settlement failed')
        await asyncio.sleep(600)

@router.callback_query(F.data=='verify_join')
async def verify_join(q:CallbackQuery):
    if await joined(q.bot,q.from_user.id):
        await q.answer('تم التحقق',show_alert=True)
        save(q.from_user)
        await notify_referrer_if_new(q.bot,q.from_user.id)
        await home(q.message)
    else: await q.answer('ما قدرنا نتحقق من الاشتراك. تأكد إنك مشترك وإن البوت أدمن بالقناة.',show_alert=True)

@router.callback_query(F.data.startswith('dep:'))
async def select_deposit(q:CallbackQuery,state:FSMContext):
    await q.answer()
    if not await require_join(q.bot,q.from_user.id,q.message): return
    method=q.data.split(':')[1]
    if method not in ('sham','sham_usd','syriatel'): return
    await state.set_state(Input.deposit_reference)
    await state.update_data(deposit_method='sham' if method.startswith('sham') else 'syriatel',
                            deposit_usd=(method=='sham_usd'))
    await deposit_instructions(q.message,method,q.from_user.id)

@router.callback_query(F.data.startswith('depgo:'))
async def begin_deposit(q:CallbackQuery,state:FSMContext):
    # Legacy Telegram buttons still work, but no manual deposit workflow.
    method=q.data.split(':',1)[1]
    if method not in ('sham','sham_usd','syriatel'): return await q.answer()
    await select_deposit_legacy(q,state,method)

async def select_deposit_legacy(q,state,method):
    await q.answer()
    if not await require_join(q.bot,q.from_user.id,q.message): return
    await state.set_state(Input.deposit_reference)
    await state.update_data(deposit_method='sham' if method.startswith('sham') else 'syriatel',deposit_usd=method=='sham_usd')
    await q.message.answer('🔢 أرسل رقم عملية التحويل فقط للتحقق التلقائي:')

async def api_syria_find(method, reference):
    if not API_SYRIA_KEY:
        raise RuntimeError('API_SYRIA_KEY missing')
    if method=='syriatel':
        account=API_SYRIA_SYRIATEL_GSM
        params={'resource':'syriatel','action':'find_tx','tx':reference,'gsm':account,'period':'all'}
    else:
        account=API_SYRIA_SHAM_ADDRESS
        params={'resource':'shamcash','action':'find_tx','tx':reference,'account_address':account}
    if not account: raise RuntimeError('Receiving account missing')
    timeout=aiohttp.ClientTimeout(total=18)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(API_SYRIA_URL,params=params,headers={'X-Api-Key':API_SYRIA_KEY,'Accept':'application/json'}) as resp:
            if resp.status!=200: raise RuntimeError(f'API Syria HTTP {resp.status}')
            payload=await resp.json(content_type=None)
    if not isinstance(payload,dict) or payload.get('success') is not True:
        raise RuntimeError('API Syria unsuccessful response')
    data=payload.get('data')
    if not isinstance(data,dict) or type(data.get('found')) is not bool:
        raise RuntimeError('API Syria unexpected response')
    if not data['found']: return None
    tx=data.get('transaction')
    if not isinstance(tx,dict): raise RuntimeError('API Syria missing transaction')
    return tx

def validate_api_transaction(method,reference,tx,usd):
    tx_id=str(tx.get('transaction_no' if method=='syriatel' else 'tran_id','')).strip()
    if tx_id!=reference: raise ValueError('رقم العملية غير مطابق')
    try:
        amount=Decimal(str(tx.get('amount','')))
        if not amount.is_finite() or amount<=0: raise ValueError()
    except (InvalidOperation,ValueError): raise ValueError('قيمة العملية غير صالحة')
    if method=='syriatel':
        receiver=str(tx.get('to','')).strip()
        allowed={re.sub(r'\D','',x) for x in syriatel_numbers()}
        if not receiver or re.sub(r'\D','',receiver) not in allowed:
            raise ValueError('الحوالة ليست واردة إلى حساب سيريتل المعتمد')
        if amount<200: raise ValueError('أقل إيداع سيريتل 200 ليرة سورية جديدة')
        credit=amount
    else:
        currency=str(tx.get('currency','')).upper().strip()
        if currency!=('USD' if usd else 'SYP'):
            raise ValueError('عملة الحوالة لا تطابق طريقة الشحن المختارة')
        if amount<(Decimal('2') if usd else Decimal('200')):
            raise ValueError('مبلغ الحوالة أقل من الحد الأدنى')
        # ShamCash find_tx is scoped to the verified linked receiving account.
        if usd:
            rate=Decimal(str(setting('dollar_rate')).replace(',',''))
            if not rate.is_finite() or rate<=0: raise ValueError('سعر الدولار غير مضبوط')
            credit=amount*rate
        else: credit=amount
    rounded=credit.quantize(Decimal('1'),rounding=ROUND_HALF_UP)
    if rounded!=credit:
        raise ValueError('المبلغ لا يمكن تحويله بدقة إلى رصيد صحيح؛ تواصل مع الدعم')
    if not 0<int(rounded)<=1000000000: raise ValueError('المبلغ خارج الحدود المسموحة')
    return int(rounded)

@router.message(Input.deposit_reference)
async def deposit_reference(m:Message,state:FSMContext):
    ref=(m.text or '').strip()
    if not re.fullmatch(r'[0-9]{3,30}',ref):
        return await m.answer('🔢 أرسل رقم العملية بالأرقام فقط (3 إلى 30 خانة).')
    data=await state.get_data()
    method=data.get('deposit_method')
    if method not in ('sham','syriatel'): return await state.clear()
    await m.answer('⏳ جارٍ التحقق من العملية...')
    try:
        tx=await api_syria_find(method,ref)
        if tx is None: return await m.answer('❌ رقم العملية غير موجود.')
        amount=validate_api_transaction(method,ref,tx,bool(data.get('deposit_usd')))
    except ValueError as e:
        return await m.answer(f'❌ لم يتم قبول العملية: {e}')
    except Exception:
        logging.exception('API Syria deposit verification error')
        return await m.answer('⚠️ تعذّر التحقق حالياً، حاول لاحقاً. لم يُضف أي رصيد.')
    save(m.from_user)
    # Atomic transaction + unique (method, operation_id) prevents double credit.
    try:
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            cur=c.execute('INSERT INTO deposits(user_id,method,amount,operation_id,status,reviewed_by,reviewed_at) VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)',
                          (m.from_user.id,method,amount,ref,'approved',0))
            did=cur.lastrowid
            bonus_row=c.execute('SELECT id,percent,kind FROM wheel_bonuses WHERE user_id=? AND used_deposit_id IS NULL AND expires_at>? ORDER BY expires_at,id LIMIT 1',(m.from_user.id,int(time.time()))).fetchone()
            bonus_amount=0; cashback=False
            if bonus_row:
                c.execute('UPDATE wheel_bonuses SET used_deposit_id=? WHERE id=? AND used_deposit_id IS NULL',(did,bonus_row['id']))
                if bonus_row['kind']=='cashback':
                    claim_amount=amount*bonus_row['percent']//100
                    if claim_amount>0:
                        c.execute('INSERT OR IGNORE INTO cashback_claims(user_id,deposit_id,deposit_amount,cashback_amount) VALUES(?,?,?,?)',(m.from_user.id,did,amount,claim_amount))
                        cashback=True
                else: bonus_amount=amount*bonus_row['percent']//100
            new=add_local_balance(c,m.from_user.id,amount+bonus_amount,0)
            earned_points=amount//500
            if earned_points:
                award=c.execute('INSERT OR IGNORE INTO loyalty_deposit_awards(deposit_id,user_id,points) VALUES(?,?,?)',(did,m.from_user.id,earned_points))
                if award.rowcount: c.execute('UPDATE users SET points=points+? WHERE id=?',(earned_points,m.from_user.id))
            c.execute('INSERT OR IGNORE INTO wheel_spins(deposit_id,user_id) VALUES(?,?)',(did,m.from_user.id))
    except sqlite3.IntegrityError:
        await state.clear()
        return await m.answer('⚠️ رقم العملية مستخدم مسبقاً، ولا يمكن شحنه مرتين.')
    except Exception:
        logging.exception('Atomic automatic deposit credit failed')
        return await m.answer('⚠️ تعذّرت إضافة الرصيد حالياً. حاول لاحقاً، ولم تُحتسب العملية.')
    await state.clear()
    msg=f'✅ تم التحقق من العملية وإضافة {amount:,} ل.س إلى رصيدك.\n💰 رصيدك الحالي: {new:,} ل.س'
    if bonus_amount: msg+=f'\n🎁 بونص الإيداع: +{bonus_amount:,} ل.س'
    if cashback: msg+='\n💸 تم تفعيل الكاش باك وفق شروطه.'
    if earned_points: msg+=f'\n🌟 نقاط ولاء مكتسبة: {earned_points}'
    await m.answer(msg)

@router.callback_query(F.data.startswith('dreview:'))
async def review_deposit(q:CallbackQuery):
    return await q.answer('المراجعة اليدوية للإيداعات معطّلة؛ الإيداع عبر التحقق التلقائي فقط.',show_alert=True)
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
            # Redeem exactly one unexpired, unused bonus on this approved deposit.
            bonus_row=c.execute('SELECT id,percent,kind FROM wheel_bonuses WHERE user_id=? AND used_deposit_id IS NULL AND expires_at>? ORDER BY expires_at,id LIMIT 1',(r['user_id'],int(time.time()))).fetchone()
            bonus_amount=0;claim_id=None;claim_amount=0
            if bonus_row:
                c.execute('UPDATE wheel_bonuses SET used_deposit_id=? WHERE id=? AND used_deposit_id IS NULL',(did,bonus_row['id']))
                if bonus_row['kind']=='cashback':
                    # Cashback = compensation: 5% of this deposit, payable only if the user loses it (admin verifies).
                    claim_amount=r['amount']*bonus_row['percent']//100
                    if claim_amount>0: claim_id=c.execute('INSERT OR IGNORE INTO cashback_claims(user_id,deposit_id,deposit_amount,cashback_amount) VALUES(?,?,?,?)',(r['user_id'],did,r['amount'],claim_amount)).lastrowid
                else:
                    bonus_amount=r['amount']*bonus_row['percent']//100
            new=add_local_balance(c,r['user_id'],r['amount']+bonus_amount,q.from_user.id)
            earned_points = r['amount'] // 500
            if earned_points > 0:
                award = c.execute('INSERT OR IGNORE INTO loyalty_deposit_awards(deposit_id,user_id,points) VALUES(?,?,?)', (did,r['user_id'],earned_points))
                if award.rowcount:
                    c.execute('UPDATE users SET points=points+? WHERE id=?', (earned_points,r['user_id']))
            c.execute('INSERT OR IGNORE INTO wheel_spins(deposit_id,user_id) VALUES(?,?)',(did,r['user_id']))
            if r['method']=='sham': c.execute('INSERT OR IGNORE INTO sham_verified(user_id,account,holder) VALUES(?,?,?)',(r['user_id'],r['sender_account'],r['sender_name']))
    await q.answer('تمت معالجة الطلب')
    try: await q.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    note=''
    if action=='approve':
        note=f'\nرصيدك الداخلي الآن: {new:,} ل.س'
        if bonus_amount: note+=f'\n🎁 بونص العجلة 5%: +{bonus_amount:,} ل.س (أُضيفت لرصيدك)'
        if claim_id: note+='\n💸 كاش باك مفعّل: إذا لم تقم بأي سحب خلال أسبوع من الآن يُضاف لك تلقائياً تعويض 5% من إيداعاتك خلال هذا الأسبوع.'
        note+=f'\n🌟 نقاط الولاء المكتسبة: {earned_points} (نقطة لكل 500 ليرة سورية جديدة)'
    try: await q.bot.send_message(r['user_id'],f'{"✅ تمت الموافقة على" if action=="approve" else "❌ تم رفض"} طلب الإيداع #{did}.'+note)
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
        return await send_admin_panel(q.message)
    if label == '👥 المستخدمين':
        if not admin(q.from_user): return await q.answer('غير مصرح', show_alert=True)
        return await show_user_list(q.message, 0)
    if label in ADMIN_MENUS and label != '🌟 نقاط الولاء':
        if not admin(q.from_user): return await q.answer('غير مصرح', show_alert=True)
        title, rows=ADMIN_MENUS[label]
        return await q.message.edit_text(admin_menu_text(label) or title, reply_markup=keyboard(rows))
    if label == '🏠 القائمة الرئيسية':
        return await go_home(m, state)
    if label == LEGACY_BONUS_LABEL:  # stale menu button: just refresh the menu
        return await go_home(m, state)
    if label == REFUND_LABEL:
        return await refund_last_withdrawal(q.message,bot,q.from_user)
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
        u=c.execute('SELECT points FROM users WHERE id=?',(m.from_user.id,)).fetchone()
    pts=u['points'] if u else 0
    await m.answer(loyalty_menu_text(pts),reply_markup=loyalty_exchange_keyboard(pts))

async def loyalty_exchange(q:CallbackQuery):
    key=q.data.split(':',1)[1]
    prize=next((p for p in loyalty_prizes() if p['key']==key),None)
    if not prize: return await q.answer('تم تحديث قائمة الاستبدال، افتحها من جديد.',show_alert=True)
    uid=q.from_user.id; cost=prize['cost']; extra=''
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        if not c.execute('UPDATE users SET points=points-? WHERE id=? AND points>=?',(cost,uid,cost)).rowcount:
            c.rollback()
            return await q.answer('❌ نقاط الولاء غير كافية',show_alert=True)
        if key=='spin':
            did=c.execute('SELECT COALESCE(MIN(deposit_id),0)-1 FROM wheel_spins WHERE deposit_id<0').fetchone()[0]
            c.execute('INSERT INTO wheel_spins(deposit_id,user_id) VALUES(?,?)',(did,uid))
            result='🎡 تمت إضافة لفة مجانية لرصيد لفاتك. افتح «اللفة المجانية» لاستخدامها.'
        elif key=='gift':
            while True:
                code='LV'+secrets.token_hex(4).upper()+'SHEIKH'
                if not c.execute('SELECT 1 FROM gift_codes WHERE code=?',(code,)).fetchone(): break
            c.execute('INSERT INTO gift_codes(code,amount,max_uses) VALUES(?,?,1)',(code,prize['amount']))
            result=f'🎁 كود هدية بقيمة {prize["amount"]:,} ل.س:\n<code>{code}</code>\nاستخدمه من زر «كود هدية» (صالح لاستخدام واحد).'
        elif key=='balance':
            bal=add_local_balance(c,uid,prize['amount'],0)
            result=f'💰 تمت إضافة {prize["amount"]:,} ل.س إلى رصيدك الداخلي. رصيدك الآن: {bal:,} ل.س'
        else:
            c.execute('UPDATE users SET free_withdrawals=free_withdrawals+1 WHERE id=?',(uid,))
            result=f'💸 حصلت على «سحب بدون عمولة» لمرة واحدة، يُطبّق تلقائياً على أول طلب سحب بمبلغ حتى {int_setting("free_withdraw_max",10000):,} ليرة سورية جديدة. المبالغ الأكبر تُحسب بالعمولة العادية.'
        points=c.execute('SELECT points FROM users WHERE id=?',(uid,)).fetchone()['points']
        free_now=c.execute('SELECT free_withdrawals FROM users WHERE id=?',(uid,)).fetchone()['free_withdrawals']
        c.execute('INSERT INTO audit(actor,action,details) VALUES(?,?,?)',(uid,'loyalty_prize_exchange',f'{key}: {cost} points'))
    if key=='nofee' and ADMIN_CHAT_ID:
        fu=q.from_user; from html import escape
        try:
            await q.bot.send_message(ADMIN_CHAT_ID,'💸 <b>استبدال «سحب بدون عمولة»</b>\n━━━━━━━━━━━━━━━━\n'
                f'👤 الاسم: {escape(fu.first_name or "-")}\n• اليوزر: {("@"+escape(fu.username)) if getattr(fu,"username",None) else "-"}\n• الآيدي: <code>{uid}</code>\n'
                f'⭐ النقاط المخصومة: {cost}\n🌟 نقاطه المتبقية: {points:,}\n🎟️ سحبات مجانية متاحة له الآن: {free_now}\n🕒 {datetime.now(DAMASCUS).strftime("%Y-%m-%d %H:%M")} (توقيت دمشق)',parse_mode='HTML')
        except Exception: logging.exception('Admin notification for fee-free withdrawal failed')
    await q.answer('تم الاستبدال بنجاح ✅',show_alert=True)
    await q.message.answer(f'✅ تم استبدال {cost} نقطة.\n{result}\n🌟 نقاطك المتبقية: {points:,}',parse_mode='HTML')
    await q.message.answer(loyalty_menu_text(points),reply_markup=loyalty_exchange_keyboard(points))

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

LOYALTY_SETTINGS=[('تكلفة لفة العجلة (نقاط)','loyalty_cost_spin'),('تكلفة كود الهدية (نقاط)','loyalty_cost_gift'),('قيمة كود الهدية (ل.س)','loyalty_gift_amount'),('تكلفة رصيد البوت (نقاط)','loyalty_cost_balance'),('قيمة رصيد البوت (ل.س)','loyalty_balance_amount'),('تكلفة سحب بدون عمولة (نقاط)','loyalty_cost_nofee')]

@router.message(F.text == '🎁 تعديل جوائز نقاط الولاء')
async def loyalty_prizes_admin(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    await state.clear()
    listing='\n'.join(f'{t}: {setting(k)}' for t,k in LOYALTY_SETTINGS)
    await m.answer('🎁 جوائز نقاط الولاء (لفة، كود هدية، رصيد، سحب بدون عمولة)\n'+listing+'\n\nاضغط على الخيار لتعديل قيمته:',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t,callback_data='ac:cfg:'+k)] for t,k in LOYALTY_SETTINGS]))

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
    await m.answer(report_text(),reply_markup=keyboard([['↩️ رجوع للوحة الأدمن']]))

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
    await m.answer('المستخدم غير موجود.')

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
    await m.answer('✅ تم تحديث حالة المستخدم.')

@router.message(F.text == '⚙️ حالة البوت (تشغيل/إيقاف)')
async def toggle(m:Message):
    if not admin(m.from_user): return
    v='0' if setting('enabled')=='1' else '1'
    with db() as c: c.execute("UPDATE settings SET value=? WHERE key='enabled'",(v,))
    audit(m.from_user.id,'bot_enabled',v)
    await m.answer('🟢 تم تشغيل البوت — المستخدمون يستطيعون استخدامه الآن.' if v=='1' else '⏸️ تم إيقاف البوت — المستخدمون لا يستطيعون استخدامه (الأدمن يعمل).')

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
    await m.answer('✅ تم تحديث نص العروض.')

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
    await m.answer(f'✅ تم الإرسال إلى {sent} من {len(ids)} مستخدم.')

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

DAMASCUS=timezone(timedelta(hours=3))  # display time for the referral schedule (Syria, UTC+3)
REFERRAL_PERIOD=10*86400

REFERRAL_TEXT=(
 'نظام احالات Ichancy الشيخ الانكليزي\n'
 'يقدّم لك فرصة لدخل إضافي كل 10 أيام .\n'
 'كن وكيلاً معنا بأبسط طريقة\n'
 'إحصل على نسبة ثابتة لكل عمليات الشحن والتعبئة القادمة عن طريق رابط احالتك ضمن البوت \n'
 '.....\n'
 '1-عند الدخول الى البوت قم بنسخ رابط الاحالة الخاص بك عن طريق الضغط على خيار رابط الاحالة الخاص بي\n'
 '2- عندما تقوم بنشر رابط احالتك ويقوم أحد بالتسجيل عن طريقة سنبدأ بحساب نسبة ثابتة لجميع عمليات السحب والتعبئة عن طريقك . \n'
 '3-يمكن الاطلاع على عدد الاحالات التي قامت بالتسجيل من خلال الرابط الخاص بك عن طريق الضغط على خيار عدد الاحالات الخاصة بك خلال المسابقة الحالية \n'
 '4- يتم حساب الارباح عند وجود 3 إحالات نشطة او أكثر\n'
 'ماذا تنتظر...! \n'
 'توزيع النسب كل 10 أيام\n')

def referral_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🔗 رابط الإحالة الخاص بي',callback_data='ref:copy'),InlineKeyboardButton(text='📤 مشاركة الرابط',callback_data='ref:share')],
        [InlineKeyboardButton(text='🏠 القائمة الرئيسية',callback_data='ref:home')]])

def next_distribution_ts():
    try: return int(setting('referral_next_distribution'))
    except (TypeError,ValueError): return int(datetime(2026,10,28,19,0,tzinfo=DAMASCUS).timestamp())

def referral_screen_text(uid,link,now=None):
    now=int(now if now is not None else time.time())
    with db() as c: n=c.execute('SELECT COUNT(*) FROM users WHERE referrer=?',(uid,)).fetchone()[0]
    nxt=next_distribution_ts(); left=max(0,nxt-now)
    d,rem=divmod(left,86400); h,rem=divmod(rem,3600); mi=rem//60
    when=datetime.fromtimestamp(nxt,DAMASCUS).strftime('%Y-%m-%d %H:%M:%S')
    return (REFERRAL_TEXT+f'\nعدد الاحالات التابعة لك: {n}\nرابط الإحالة الخاص بك: {link}\n\nالموعد القادم لتوزيع الاحالات: \n{when}\n{d} يوم {h} ساعة {mi} دقيقة')

async def referral_screen(message,bot,uid):
    me=await bot.get_me(); link=f'https://t.me/{me.username}?start=ref_{uid}'
    await message.answer(referral_screen_text(uid,link),reply_markup=referral_keyboard())

@router.callback_query(F.data.startswith('ref:'))
async def referral_click(q:CallbackQuery,bot:Bot,state:FSMContext):
    action=q.data[4:]; uid=q.from_user.id
    if action not in ('home','copy','share'):  # buttons removed in V41 (old messages may still carry them)
        return await q.answer('تم تحديث نظام الإحالات، افتحه من جديد من القائمة الرئيسية.',show_alert=True)
    if not await require_join(bot,uid,q.message): return await q.answer()
    await q.answer()
    me=await bot.get_me(); link=f'https://t.me/{me.username}?start=ref_{uid}'
    if action=='home': return await home(q.message)
    if action=='copy': return await q.message.answer('📋 رابطك للنسخ:\n'+link)
    if action=='share': return await q.message.answer('📤 شارك الرابط التالي مع أصدقائك:\n'+link)

def referral_plan(c,since,until):
    """Commission plan for approved bot deposits made by referred users in (since, until], never paid before.
    A referral is 'active' when it has at least one approved deposit in the period; a referrer needs >= referral_min_active
    active referrals. Commission = referral_percent % of those deposits."""
    cfg=lambda k,d: (c.execute('SELECT value FROM settings WHERE key=?',(k,)).fetchone() or [d])[0]
    pct=float(cfg('referral_percent','5') or 5); need=int(float(cfg('referral_min_active','3') or 3))
    rows=c.execute("""SELECT d.id,d.user_id,d.amount,u.referrer FROM deposits d JOIN users u ON u.id=d.user_id JOIN users r ON r.id=u.referrer
        WHERE d.status='approved' AND r.banned=0 AND u.referrer<>d.user_id
        AND CAST(strftime('%s',d.reviewed_at) AS INTEGER)>? AND CAST(strftime('%s',d.reviewed_at) AS INTEGER)<=?
        AND d.id NOT IN (SELECT deposit_id FROM referral_paid_deposits) ORDER BY d.id""",(since,until)).fetchall()
    groups={}
    for r in rows: groups.setdefault(r['referrer'],{}).setdefault(r['user_id'],[]).append((r['id'],r['amount']))
    eligible=[];skipped=0
    for ref,users in groups.items():
        if len(users)<need: skipped+=1; continue
        per_user={u:sum(a for _,a in lst) for u,lst in users.items()}
        comm={u:v*int(pct*100)//10000 for u,v in per_user.items()}
        total=sum(comm.values())
        if total<=0: skipped+=1; continue
        eligible.append(dict(referrer=ref,active=len(users),deposits=sum(per_user.values()),commission=total,comm=comm,deposit_ids=[i for lst in users.values() for i,_ in lst]))
    return dict(pct=pct,need=need,eligible=eligible,skipped=skipped)

def fmt_local(ts): return datetime.fromtimestamp(ts,DAMASCUS).strftime('%Y-%m-%d %H:%M')

async def referral_distribution_preview(message):
    now=int(time.time()); last=int(setting('referral_last_distribution') or 0)
    with db() as c: plan=referral_plan(c,last,now)
    total=sum(e['commission'] for e in plan['eligible'])
    lines=[f"📤 توزيع أرباح الإحالات\n🗓 الفترة: {fmt_local(last)} ← {fmt_local(now)} (توقيت دمشق)\n📈 النسبة: {plan['pct']:g}% من إيداعات المُحالين المعتمدة\n✅ شرط الاستحقاق: {plan['need']} إحالات نشطة أو أكثر (إحالة نشطة = لها إيداع معتمد ضمن الفترة)\n\n👥 وكلاء مستحقون: {len(plan['eligible'])}\n⛔ غير مستوفين للشرط: {plan['skipped']}\n💰 إجمالي التوزيع: {total:,} SYP\n🗓 الموعد الحالي المسجّل للتوزيع: {fmt_local(next_distribution_ts())}"]
    for e in sorted(plan['eligible'],key=lambda x:-x['commission'])[:15]: lines.append(f"• {e['referrer']}: {e['commission']:,} SYP ({e['active']} إحالات نشطة)")
    if not plan['eligible']: return await message.answer('\n'.join(lines)+'\n\nلا يوجد شيء للتوزيع حالياً.',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✖️ إغلاق',callback_data='refdist:cancel')]]))
    await message.answer('\n'.join(lines)+'\n\n⚠️ التأكيد يضيف المبالغ لأرصدة الوكلاء فوراً ولا يمكن التراجع.',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ تأكيد التوزيع',callback_data=f'refdist:confirm:{last}'),InlineKeyboardButton(text='✖️ إلغاء',callback_data='refdist:cancel')]]))

@router.callback_query(F.data.startswith('refdist:'))
async def referral_distribution_click(q:CallbackQuery):
    if not admin(q.from_user): return await q.answer('غير مصرح',show_alert=True)
    parts=q.data.split(':')
    if parts[1]=='cancel':
        await q.answer('تم الإلغاء')
        try: await q.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        return
    if parts[1]!='confirm' or len(parts)<3: return await q.answer('طلب غير صحيح',show_alert=True)
    try: token=int(parts[2])
    except ValueError: return await q.answer('طلب غير صحيح',show_alert=True)
    now=int(time.time()); paid=[]
    try:
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            last=int((c.execute("SELECT value FROM settings WHERE key='referral_last_distribution'").fetchone() or ['0'])[0] or 0)
            if last!=token: return await q.answer('تم التوزيع مسبقاً أو تغيّرت الفترة. افتح التوزيع من جديد.',show_alert=True)
            plan=referral_plan(c,last,now)
            for e in plan['eligible']:
                add_local_balance(c,e['referrer'],e['commission'],q.from_user.id)
                for ref_user,amt in e['comm'].items():
                    if amt>0: c.execute("INSERT INTO referral_commissions(referrer_id,referred_id,amount,status,paid_at) VALUES(?,?,?,'paid',CURRENT_TIMESTAMP)",(e['referrer'],ref_user,amt))
                for did in e['deposit_ids']: c.execute('INSERT INTO referral_paid_deposits(deposit_id,referrer_id,amount) VALUES(?,?,0)',(did,e['referrer']))
                paid.append((e['referrer'],e['commission']))
            old_next=next_distribution_ts(); new_next=old_next+REFERRAL_PERIOD
            while new_next<=now: new_next+=REFERRAL_PERIOD
            c.execute("INSERT INTO settings(key,value) VALUES('referral_last_distribution',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(now),))
            c.execute("INSERT INTO settings(key,value) VALUES('referral_next_distribution',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(new_next),))
    except Exception:
        logging.exception('Referral distribution failed')
        return await q.answer('تعذّر التوزيع، لم يتم تغيير شيء.',show_alert=True)
    audit(q.from_user.id,'referral_distribution',f'{len(paid)} referrers, {sum(a for _,a in paid)} SYP')
    await q.answer('تم التوزيع')
    try: await q.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    for ref,amt in paid:
        try: await q.bot.send_message(ref,f'💸 تم توزيع أرباح الإحالات: أُضيف {amt:,} SYP إلى رصيدك الداخلي.\n🗓 موعد التوزيع القادم: {fmt_local(new_next)}')
        except Exception: logging.exception('Referral payout notification failed for %s',ref)
    await q.message.answer(f'✅ تم توزيع أرباح الإحالات على {len(paid)} وكيل، بإجمالي {sum(a for _,a in paid):,} SYP.\n🗓 الموعد القادم: {fmt_local(new_next)}')

SUPPORT_BOT_TEXT='@kapossupport®️\n\nمعلوماتك بأمان تام لدينا …✔️\n\nيرجى التواصل معنا عند حدوث أي خطأ'
SUPPORT_SITE_TEXT=('في حال ورود مشكلة تقنية ضمن الموقع يرجى التّواصل :\n'
 'مع الدّعم الرسمي للموقع عبر الرابط \nhttps://direct.lc.chat/16220229/\n'
 'أو عبر صفحة الموقع الرّسمية على منصّة Faecbook . \nhttps://www.facebook.com/ichancy.co?mibextid=ZbWKwL')

def contact_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='مشكلة تقنية ضمن البوت',callback_data='sup:bot')],
        [InlineKeyboardButton(text='مشكلة تقنية ضمن الموقع',callback_data='sup:site')],
        [InlineKeyboardButton(text='القائمة الرئيسية',callback_data=BUTTON_IDS['🏠 القائمة الرئيسية'])]])

async def contact_menu(m):
    await m.answer('الدعم',reply_markup=contact_keyboard())

@router.callback_query(F.data.startswith('sup:'))
async def contact_click(q:CallbackQuery,bot:Bot):
    if not admin(q.from_user) and not await require_join(bot,q.from_user.id,q.message): return await q.answer()
    await q.answer()
    if q.data=='sup:bot': return await q.message.answer(SUPPORT_BOT_TEXT)
    if q.data=='sup:site': return await q.message.answer(SUPPORT_SITE_TEXT)

@router.message(F.text.in_(ALL))
async def services(m:Message,bot:Bot,state:FSMContext=None):
    save(m.from_user)
    with db() as c: u=c.execute('SELECT banned FROM users WHERE id=?',(m.from_user.id,)).fetchone()
    if u and u['banned']: return await m.answer('حسابك محظور من استخدام الخدمات.')
    if setting('enabled')!='1' and not admin(m.from_user): return await m.answer('البوت متوقف مؤقتاً.')
    if m.text=='💵 اللفة المجانية':
        url=os.getenv('MINIAPP_URL','').strip()
        if not url: return await m.answer('تطبيق العجلة غير مفعّل بعد. أضف MINIAPP_URL في Railway.')
        rows=[[InlineKeyboardButton(text='🎡 افتح عجلة الحظ',web_app=WebAppInfo(url=url))]]
        return await m.answer('🎡 عجلة Al_Basha-ichancy\nيجب ان تشحن للحصول على لفة مجانية',reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    if m.text=='💌 تواصل معنا': return await contact_menu(m)
    if m.text=='💸 نظام الإحالات':
        return await referral_screen(m,bot,m.from_user.id)
    if state is not None:
        if m.text=='🎟️ إهداء رصيد': return await transfer_start(m,state)
        if m.text=='🎁 كود هدية': return await gift_start(m,state)
        if m.text=='📝 رسالة للأدمن': return await support_start(m,state)
    if m.text==REFUND_LABEL: return await refund_last_withdrawal(m,bot,m.from_user)
    if m.text=='🟥 Ichancy': return await m.answer('خدمات Ichancy الخارجية غير متصلة حالياً؛ بانتظار الربط الرسمي.')
    if m.text=='💸 شحن رصيد البوت': return await deposit_menu(m)
    if m.text=='💰 سحب رصيد البوت': return await withdrawal_menu(m,m.from_user.id)
    lookup={'💜 الشروط والأحكام':'terms','⚠️ الشروحات':'tutorials','💵 اللفة المجانية':'free_spin','💌 تواصل معنا':'contact_url','↗️ Vpn لتشغيل كامل أقسام الموقع':'vpn_url','↗️ ichancy apk':'apk_url','🎰 ألعاب Ichancy':'games_url','⭐ دخول مباشر للألعاب':'direct_url'}
    if m.text in lookup:
        val=setting(lookup[m.text]); return await m.answer(val or 'لم يضف الأدمن محتوى هذا القسم بعد.',reply_markup=keyboard([['🏠 القائمة الرئيسية']]))
    if m.text=='✅ السجل': return await history_menu(m)
    await m.answer('هذا القسم معلوماتي فقط، وليس متصلاً بـ Ichancy.')

@router.message(F.text.in_(ADMIN_ALL))
async def admin_placeholder(m:Message):
    if not admin(m.from_user): return
    await m.answer(f'{m.text}\n\n🛠️ هذا القسم ظاهر حسب التصميم المرجعي، لكنه غير مفعّل بعد. لا تتم أي حركة مالية أو سحب بيانات غير مصرح به.')

# ---------------------------------------------------------------- history (deposits / withdrawals)
HIST_PAGE=5
DEP_NAMES={'sham':'Sham Cash Auto ⚡(USD , SYP)','syriatel':'Syriatel Cash 🟢'}
WD_NAMES={'sham_usd':'💲 Sham Cash (دولار أمريكي)','sham_syp':'💲 Sham Cash (ليرة سورية)','syriatel':'Syriatel Cash 🟢'}
HIST_STATUS={'pending':'⏳ قيد المراجعة','rejected':'❌ مرفوض','refunded':'↩️ تم الاسترداد'}

def local_time(ts):
    try: return (datetime.strptime(str(ts)[:19],'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)+timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError: return str(ts)

def history_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='سجل الشحن',callback_data='hist:dep:1'),InlineKeyboardButton(text='سجل السحب',callback_data='hist:wd:1')],
        [InlineKeyboardButton(text='القائمة الرئيسية',callback_data=BUTTON_IDS['🏠 القائمة الرئيسية'])]])

async def history_menu(m):
    await m.answer('السجل',reply_markup=history_menu_keyboard())

def history_page(uid,kind,page):
    with db() as c:
        if kind=='dep': rows=c.execute('SELECT method,amount,status,requested_at FROM deposits WHERE user_id=? ORDER BY id DESC',(uid,)).fetchall()
        else: rows=c.execute('SELECT method,amount_syp AS amount,status,requested_at FROM withdrawals WHERE user_id=? ORDER BY id DESC',(uid,)).fetchall()
    total=len(rows)
    if not total: return 'لا توجد عمليات بعد.',None
    pages=(total+HIST_PAGE-1)//HIST_PAGE; page=min(max(page,1),pages)
    names=DEP_NAMES if kind=='dep' else WD_NAMES
    out=[f'{total} Transactions','']
    for i,r in enumerate(rows[(page-1)*HIST_PAGE:page*HIST_PAGE],(page-1)*HIST_PAGE+1):
        out+= [f'#{i}',names.get(r['method'],r['method']),f"المبلغ: {float(r['amount']):.1f}",local_time(r['requested_at'])]
        if r['status'] in HIST_STATUS: out.append(HIST_STATUS[r['status']])
        out+=['------------------------','']
    kb=None
    if pages>1:
        lo=max(1,min(page-10,pages-19)) if pages>20 else 1; hi=min(pages,lo+19) if pages>20 else pages
        nums=list(range(lo,hi+1))
        btns=[InlineKeyboardButton(text=(f'[{n}]' if n==page else str(n)),callback_data=f'hist:{kind}:{n}') for n in nums]
        kb=InlineKeyboardMarkup(inline_keyboard=[btns[i:i+5] for i in range(0,len(btns),5)])
    return '\n'.join(out).rstrip(),kb

@router.callback_query(F.data.startswith('hist:'))
async def history_click(q:CallbackQuery):
    try: _,kind,page=q.data.split(':'); page=int(page)
    except ValueError: return await q.answer()
    if kind not in ('dep','wd'): return await q.answer()
    text,kb=history_page(q.from_user.id,kind,page)
    await q.answer()
    try: await q.message.edit_text(text,reply_markup=kb)
    except Exception: await q.message.answer(text,reply_markup=kb)

def user_list_markup(page, total, records):
    rows=[]
    for u in records:
        name=(u['first_name'] or u['username'] or 'مستخدم').replace('\n',' ')[:28]
        rows.append([InlineKeyboardButton(text=f"👤 {name} | {u['id']}",callback_data=f"ud:{u['id']}:{page}")])
    nav=[]
    if page>0: nav.append(InlineKeyboardButton(text='⬅️ السابق',callback_data=f'ul:{page-1}'))
    if (page+1)*8<total: nav.append(InlineKeyboardButton(text='التالي ➡️',callback_data=f'ul:{page+1}'))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton(text='🔎 بحث عن مستخدم (آيدي أو يوزر)',callback_data='ac:🔎 البحث عن مستخدم')])
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
    uid=m.from_user.id
    with db() as c: u=c.execute('SELECT banned FROM users WHERE id=?',(uid,)).fetchone()
    if u and u['banned']: return await m.answer('حسابك محظور من استخدام الخدمات.')
    await state.set_state(Input.user_transfer)
    await m.answer(f'🎟️ إهداء رصيد البوت الداخلي\n💰 رصيدك الحالي: {balance_of(uid):,} ل.س\n\nأرسل آيدي المستلم ثم المبلغ في رسالة واحدة:\n<code>123456789 5000</code>\n\n• يجب أن يكون المستلم قد فتح البوت مرة واحدة على الأقل.\n• للإلغاء أرسل /cancel',parse_mode='HTML')

@router.message(Input.user_transfer)
async def transfer_finish(m:Message,state:FSMContext):
    import re, unicodedata
    raw=''.join(str(unicodedata.decimal(ch)) if ch.isdecimal() else ch for ch in (m.text or ''))
    raw=raw.replace('٬','').replace(',','')
    mt=re.fullmatch(r'\s*(\d+)\s+(\d+)\s*',raw)
    if not mt: return await m.answer('❌ الصيغة غير صحيحة. أرسل الآيدي ثم المبلغ مفصولين بمسافة، مثال:\n123456789 5000\nللإلغاء أرسل /cancel')
    uid,amount=int(mt.group(1)),int(mt.group(2)); me=m.from_user.id
    if amount<=0 or amount>100000000: return await m.answer('❌ المبلغ غير صحيح.')
    if uid==me: return await m.answer('❌ لا يمكنك إهداء رصيد لنفسك.')
    err=None
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        s_row=c.execute('SELECT banned,bot_balance FROM users WHERE id=?',(me,)).fetchone()
        r_row=c.execute('SELECT banned FROM users WHERE id=?',(uid,)).fetchone()
        if not s_row or s_row['banned']: err='❌ حسابك غير متاح.'
        elif not r_row: err='❌ هذا الآيدي غير مسجل في البوت. يجب أن يفتح المستلم البوت مرة واحدة أولاً.'
        elif r_row['banned']: err='❌ حساب المستلم غير متاح.'
        elif s_row['bot_balance']<amount: err=f'❌ رصيدك غير كافٍ. رصيدك الحالي: {s_row["bot_balance"]:,} ل.س'
        else:
            new=add_local_balance(c,me,-amount,me)
            add_local_balance(c,uid,amount,me)
    if err: return await m.answer(err)
    await state.clear()
    await m.answer(f'✅ تم إهداء {amount:,} ل.س إلى {uid}.\n💰 رصيدك المتبقي: {new:,} ل.س')
    try: await m.bot.send_message(uid,f'🎟️ وصلك إهداء {amount:,} ل.س من رصيد البوت الداخلي.\n👤 من: {me}')
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
    if action==PENDING_LABEL: return await message.answer(pending_text(),reply_markup=keyboard([['↩️ رجوع للوحة الأدمن']]))
    if action==FEES_LABEL: return await message.answer(fees_text(),reply_markup=fees_keyboard())
    if action=='📊 تقرير': return await message.answer(report_text(),reply_markup=keyboard([['↩️ رجوع للوحة الأدمن']]))
    if action==DIST_LABEL: return await referral_distribution_preview(message)
    if action in ('content','📝 إدارة المحتوى والروابط'):
        keys=[('شروط الاستخدام','terms'),('الشروحات','tutorials'),('رابط التواصل','contact_url'),('رابط VPN','vpn_url'),('رابط APK','apk_url'),('رابط الألعاب','games_url'),('الدخول المباشر','direct_url'),('اللفة المجانية','free_spin')]
        return await message.edit_text('📝 تعديل محتوى الأقسام والروابط',reply_markup=InlineKeyboardMarkup(inline_keyboard=[*[ [InlineKeyboardButton(text=label,callback_data='ac:cfg:'+key)] for label,key in keys], [InlineKeyboardButton(text='↩️ لوحة الأدمن',callback_data=BUTTON_IDS['↩️ رجوع للوحة الأدمن'])]]))
    if action.startswith('cfg:'):
        key=action[4:]
        await state.set_state(Input.admin_config)
        await state.update_data(config_key=key)
        return await message.answer('✏️ '+(CONFIG_NAMES[key][0]+'\n'+CONFIG_NAMES[key][1] if key in CONFIG_NAMES else f'أرسل القيمة الجديدة لـ {key}.')+'\nللإلغاء أرسل /cancel')
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
        return await message.answer('🟢 تم تشغيل البوت — المستخدمون يستطيعون استخدامه الآن.' if v=='1' else '⏸️ تم إيقاف البوت — المستخدمون لا يستطيعون استخدامه (الأدمن يعمل).')
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
    if key in CONFIG_NAMES:
        try:
            v=float(value)
            if key=='withdraw_fee_percent' and not 0<=v<=100: raise ValueError()
            if key!='withdraw_fee_percent' and (v<1 or not v.is_integer()): raise ValueError()
        except ValueError: return await m.answer('❌ القيمة غير صحيحة. '+CONFIG_NAMES[key][1])
    if key.startswith('loyalty_'):
        try:
            if not (1<=int(value)<=100000000): raise ValueError()
        except ValueError: return await m.answer('أرسل رقماً صحيحاً موجباً.')
    if key in ('dollar_rate','cashback','referral_reward','referral_percent','referral_min_active','referral_min_transfers','referral_min_days','referral_maturity_days','referral_monthly_cap','referral_total_cap'):
        try:
            v=float(value)
            if v<0 or (key=='dollar_rate' and v<=0) or (key in ('cashback','referral_percent') and v>100) or (key.startswith('referral_') and key!='referral_percent' and not v.is_integer()): raise ValueError()
        except ValueError: return await m.answer('القيمة الرقمية غير صحيحة.')
    with db() as c: c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))
    audit(m.from_user.id,'config_updated',key)
    await state.clear()
    await m.answer(f'✅ تم الحفظ: {CONFIG_NAMES[key][0] if key in CONFIG_NAMES else key} = {value}',reply_markup=admin_actions_keyboard())

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
    await m.answer(f'✅ تم إنشاء كود الهدية\n🎟️ {code}\n💰 القيمة: {amount}\n👥 عدد المستخدمين: {uses}\nالرصيد داخلي فقط.')

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
    if MIGRATION_REPORT:
        msg=(f'💱 تم إرجاع الصفرين لكل المبالغ (إلغاء تحويل V45).\n• مستخدمون لديهم رصيد: {MIGRATION_REPORT["users_with_balance"]}\n• مجموع الأرصدة قبل: {MIGRATION_REPORT["balances_before"]:,}\n• مجموع الأرصدة بعد: {MIGRATION_REPORT["balances_after"]:,}\n• نسخة احتياطية قبل الإرجاع: {MIGRATION_REPORT["backup"]}\nتمت العملية مرة واحدة فقط ولن تتكرر. (النسخة الاحتياطية الأصلية .pre_currency محفوظة إن وُجدت، لأن تحويل V45 قرّب الأرصدة لأقرب ليرة.)')
        for aid in ADMIN_IDS:
            try: await bot.send_message(aid,msg)
            except Exception: logging.exception('Currency migration notice failed for %s',aid)
    await bot.set_my_commands([
        BotCommand(command='start', description='🏠 القائمة الرئيسية'),
        BotCommand(command='balance', description='💰 رصيدي في البوت'),
        BotCommand(command='cancel', description='❌ إلغاء العملية الحالية'),
    ], scope=BotCommandScopeDefault())
    dp=Dispatcher()
    router.message.middleware(MembershipMiddleware())
    dp.include_router(router)
    from wheel_server import serve
    runner=await serve()
    cashback_task=asyncio.create_task(cashback_loop(bot))
    try: await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()

if __name__=='__main__': asyncio.run(main())
