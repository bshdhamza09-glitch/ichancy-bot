"""Sheikh Telegram bot. Local loyalty ledger; no Ichancy financial API calls."""
import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove,
                           CallbackQuery, Message)
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN', '').strip()
NAME = os.getenv('BOT_NAME', 'Sheikh').strip() or 'Sheikh'
ADMIN_IDS = {int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip().isdigit()}
DB = Path(os.getenv('DATABASE_PATH', str(Path(__file__).with_name('sheikh.db'))))
GIF = Path(__file__).with_name('welcome.gif')
router = Router()

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
    ['📝 تعديل نص البونصات والعروض الحالية'],
    ['🎁 إضافة أو حذف البونص', '🎁 إدارة الجائزة الحالية'],
    ['💸 الكاش باك الأسبوعي 10%'],
    ['↩️ رجوع للوحة الأدمن'],
]
LOYALTY_ADMIN_ROWS = [
    ['➕ منح نقاط ولاء', '🎁 إنشاء جائزة ولاء'],
    ['⚡ تعجيل جوائز نقاط الولاء'],
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
REFERRAL_ADMIN_ROWS = [['💰 توزيع أرباح الإحالات'], ['↩️ رجوع للوحة الأدمن']]
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
    loyalty_claim = State()
    award_id = State()
    ban = State()
    unban = State()
    broadcast = State()
    bonus_text = State()
    support = State()
    balance_change = State()
    points_change = State()
    admin_config = State()
    user_transfer = State()
    gift_redeem = State()
    admin_code = State()
    admin_search = State()

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
        CREATE TABLE IF NOT EXISTS support_messages(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, body TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        
        ''')
        cols={r[1] for r in c.execute('PRAGMA table_info(users)')}
        if 'bot_balance' not in cols: c.execute('ALTER TABLE users ADD COLUMN bot_balance INTEGER NOT NULL DEFAULT 0')
        c.execute("INSERT OR IGNORE INTO settings VALUES ('enabled','1')")
        c.execute("INSERT OR IGNORE INTO settings VALUES ('bonuses','لا توجد عروض منشورة حالياً.')")
        for key,value in [('dollar_rate','0'),('cashback','10'),('weekly_cashback','10'),('referral_reward','0'),('terms','يرجى الالتزام بشروط استخدام البوت.'),('tutorials','لا توجد شروحات منشورة حالياً.'),('vpn_url',''),('apk_url',''),('games_url',''),('direct_url',''),('contact_url',''),('jackpot','غير متاح حالياً.'),('free_spin','غير متاح حالياً.'),('current_prize','لا توجد جائزة حالية.'),('sham_codes',''),('syriatel_codes','')]:
            c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(key,value))

def audit(actor, action, details=''):
    with db() as c:
        c.execute('INSERT INTO audit(actor,action,details) VALUES(?,?,?)',(actor,action,str(details)))

def save(u, ref=None):
    with db() as c:
        c.execute('INSERT OR IGNORE INTO users(id,username,first_name,referrer) VALUES(?,?,?,?)', (u.id,u.username,u.first_name,ref if ref != u.id else None))
        c.execute('UPDATE users SET username=?,first_name=? WHERE id=?',(u.username,u.first_name,u.id))

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

async def home(m, welcome=False):
    msg=f'🏠 أهلاً بك في بوت {NAME}\nاختر الخدمة من القائمة التالية 👇'
    if welcome and GIF.exists() and os.getenv('SEND_WELCOME_GIF','0')=='1':
        await m.answer_animation(FSInputFile(GIF), caption=msg)
    else:
        await m.answer(msg, reply_markup=keyboard(ROWS))
    if welcome and GIF.exists() and os.getenv('SEND_WELCOME_GIF','0')=='1':
        await m.answer('📋 القائمة الرئيسية',reply_markup=keyboard(ROWS))

@router.callback_query(F.data.startswith(('btn_', 'ul:', 'ud:', 'ua:', 'uc:', 'ac:', 'gift:')))
async def click_button(q: CallbackQuery, state: FSMContext, bot: Bot):
    if q.data.startswith(('ul:', 'ud:', 'ua:', 'uc:')):
        if not admin(q.from_user): return await q.answer('غير مصرح', show_alert=True)
        await q.answer()
        return await user_callback(q, state)
    if q.data.startswith('ac:'):
        if not admin(q.from_user): return await q.answer('غير مصرح',show_alert=True)
        await q.answer()
        return await admin_action(q.message.model_copy(update={'from_user':q.from_user}),state,q.from_user,q.data[3:])
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
        '🎁 إنشاء جائزة ولاء': lambda: reward_start(m, state),
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
    if label in ALL:
        return await services(m, bot)

@router.message(CommandStart())
async def start(m: Message, state:FSMContext):
    await state.clear()
    ref=None
    p=(m.text or '').split(maxsplit=1)
    if len(p)>1 and p[1].startswith('ref_'):
        try: ref=int(p[1][4:])
        except ValueError: pass
    save(m.from_user,ref)
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

@router.message(F.text == '🌟 نقاط الولاء')
async def loyalty(m:Message):
    save(m.from_user)
    with db() as c:
        u=c.execute('SELECT points FROM users WHERE id=?',(m.from_user.id,)).fetchone()
        rewards=c.execute('SELECT id,title,cost FROM rewards WHERE active=1 ORDER BY cost,id').fetchall()
        claims=c.execute('SELECT id,status FROM claims WHERE user_id=? ORDER BY id DESC LIMIT 5',(m.from_user.id,)).fetchall()
    desc='\n'.join(f"#{r['id']} — {r['title']} ({r['cost']} نقطة)" for r in rewards) or 'لا توجد جوائز متاحة حالياً.'
    history=', '.join(f"#{x['id']} {x['status']}" for x in claims) or 'لا يوجد'
    await m.answer(f"🌟 رصيد نقاطك: {u['points']}\n\n🎁 الجوائز:\n{desc}\n\n📦 طلباتك: {history}\n\nلاستبدال جائزة اضغط الزر أدناه.",reply_markup=keyboard([['🎁 استبدال نقاط'],['🏠 القائمة الرئيسية']]))

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
    await m.answer(f'🌟 إدارة الولاء\nطلبات معلّقة: {pending}\n{txt}',reply_markup=keyboard(LOYALTY_ADMIN_ROWS))

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
    await state.clear()
    await m.answer(f'تمت إضافة {pts} نقطة للمستخدم {uid}.',reply_markup=keyboard(LOYALTY_ADMIN_ROWS))

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
    await state.clear()
    await m.answer('تم تحديث حالة المستخدم.',reply_markup=keyboard(USER_ADMIN_ROWS))

@router.message(F.text == '⚙️ حالة البوت (تشغيل/إيقاف)')
async def toggle(m:Message):
    if not admin(m.from_user): return
    v='0' if setting('enabled')=='1' else '1'
    with db() as c: c.execute("UPDATE settings SET value=? WHERE key='enabled'",(v,))
    audit(m.from_user.id,'bot_enabled',v)
    await m.answer('البوت مفعّل' if v=='1' else 'البوت موقوف للمستخدمين (الأدمن يعمل).')

@router.message(F.text == '📝 تعديل نص البونصات والعروض الحالية')
async def bonus_start(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    await state.set_state(Input.bonus_text)
    await m.answer('أرسل نص العروض الجديد.',reply_markup=back())

@router.message(Input.bonus_text)
async def bonus_finish(m:Message,state:FSMContext):
    if not (m.text or '').strip(): return
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

@router.message(F.text == '📝 رسالة للأدمن')
async def support_start(m:Message,state:FSMContext):
    await state.set_state(Input.support)
    await m.answer('اكتب رسالتك للأدمن.',reply_markup=back())

@router.message(Input.support)
async def support_finish(m:Message,state:FSMContext):
    if not m.text: return await m.answer('اكتب رسالة نصية.')
    for aid in ADMIN_IDS:
        try: await m.bot.send_message(aid,f'📨 رسالة من {m.from_user.id}:\n{m.text[:3500]}')
        except Exception: logging.exception('Admin message failed')
    await state.clear()
    await m.answer('تم إرسال رسالتك.',reply_markup=keyboard(ROWS))

@router.message(F.text.in_(ALL))
async def services(m:Message,bot:Bot):
    save(m.from_user)
    with db() as c: u=c.execute('SELECT banned FROM users WHERE id=?',(m.from_user.id,)).fetchone()
    if u and u['banned']: return await m.answer('حسابك محظور من استخدام الخدمات.')
    if setting('enabled')!='1' and not admin(m.from_user): return await m.answer('البوت متوقف مؤقتاً.')
    if m.text=='💸 نظام الإحالات':
        me=await bot.get_me()
        with db() as c: n=c.execute('SELECT COUNT(*) n FROM users WHERE referrer=?',(m.from_user.id,)).fetchone()['n']
        return await m.answer(f'https://t.me/{me.username}?start=ref_{m.from_user.id}\nعدد الإحالات: {n}\nلا توجد أرباح تلقائية مفعلة.')
    if m.text=='🎁 البونصات والعروض الحالية': return await m.answer(setting('bonuses'))
    if m.text=='🟥 Ichancy': return await m.answer('خدمات Ichancy الخارجية غير متصلة حالياً؛ بانتظار الربط الرسمي.')
    if m.text in ('💸 شحن رصيد البوت','💰 سحب رصيد البوت'):
        return await m.answer('🔒 الخدمة غير مفعلة. لا يتم تنفيذ أي تحويل مالي قبل ربط الـ API الرسمي واختباره.')
    lookup={'💜 الشروط والأحكام':'terms','⚠️ الشروحات':'tutorials','🟣 الجاكبوت':'jackpot','💵 اللفة المجانية':'free_spin','💌 تواصل معنا':'contact_url','↗️ Vpn لتشغيل كامل أقسام الموقع':'vpn_url','↗️ ichancy apk':'apk_url','🎰 ألعاب Ichancy':'games_url','⭐ دخول مباشر للألعاب':'direct_url'}
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
        [InlineKeyboardButton(text='🌟 تعديل النقاط',callback_data=f'ua:points:{uid}:{page}'),InlineKeyboardButton(text='📜 سجل العمليات',callback_data=f'ua:history:{uid}:{page}')],
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
        return await show_user_detail(q.message,uid,page)
    if action=='history':
        with db() as c: rows=c.execute('SELECT delta,balance_after,created FROM bot_ledger WHERE user_id=? ORDER BY id DESC LIMIT 12',(uid,)).fetchall()
        lines='\n'.join(f"{r['created']}: {r['delta']:+d} → {r['balance_after']}" for r in rows) or 'لا توجد عمليات'
        return await q.message.edit_text(f'📜 سجل رصيد البوت للمستخدم {uid}\n{lines}',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='↩️ ملف المستخدم',callback_data=f'ud:{uid}:{page}')]]))
    if action in ('credit','debit','points'):
        await state.set_state(Input.points_change if action=='points' else Input.balance_change)
        await state.update_data(target_uid=uid,action=action,page=page)
        await q.message.edit_text(f"{'🌟 تعديل النقاط' if action=='points' else '💰 تعديل رصيد البوت'} للمستخدم {uid}\nأرسل المبلغ كعدد صحيح موجب (وحدة داخلية).",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='↩️ إلغاء',callback_data=f'uc:{uid}:{page}')]]))

@router.message(Input.balance_change)
@router.message(Input.points_change)
async def apply_internal_change(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    data=await state.get_data()
    try:
        amount=int((m.text or '').strip())
        if not 0<amount<=100000000: raise ValueError()
    except ValueError: return await m.answer('أرسل عدداً صحيحاً موجباً ضمن الحد المسموح.')
    uid,action,page=data['target_uid'],data['action'],data['page']
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT bot_balance,points FROM users WHERE id=?',(uid,)).fetchone()
        if not row: return await m.answer('المستخدم غير موجود.')
        if action=='points':
            new=row['points']+amount
            c.execute('UPDATE users SET points=? WHERE id=?',(new,uid))
        else:
            delta=amount if action=='credit' else -amount
            new=row['bot_balance']+delta
            if new<0: return await m.answer('الرصيد غير كافٍ للخصم.')
            c.execute('UPDATE users SET bot_balance=? WHERE id=?',(new,uid))
            c.execute('INSERT INTO bot_ledger(user_id,admin_id,delta,balance_after) VALUES(?,?,?,?)',(uid,m.from_user.id,delta,new))
    audit(m.from_user.id,'internal_'+action,f'{uid}:{amount}')
    await state.clear()
    await m.answer(f'✅ تمت العملية داخل البوت فقط. الرصيد/النقاط الجديدة: {new}\nلا يوجد أي تحويل إلى Ichancy.',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='↩️ ملف المستخدم',callback_data=f'ud:{uid}:{page}')]]))


# All balances in these handlers are LOCAL bot ledger balances; no Ichancy operations.
def add_local_balance(c,uid,delta,actor):
    row=c.execute('SELECT bot_balance FROM users WHERE id=?',(uid,)).fetchone()
    if not row or row['bot_balance']+delta<0: raise ValueError('المستخدم غير موجود أو الرصيد غير كافٍ')
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
    code=code.strip().upper()
    try:
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
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
    await redeem_code(m.from_user.id,m.text or '',m)

ADMIN_ACTIONS={
 '⚙️ تعديل سعر الدولار':('dollar_rate','أرسل سعر الدولار (رقم موجب).'),
 '💸 الكاش باك الأسبوعي 10%':('cashback','أرسل نسبة الكاش باك للعرض (0 إلى 100).'),
 '💰 توزيع أرباح الإحالات':('referral_reward','أرسل مكافأة الإحالة الداخلية لكل مستخدم جديد (0 لتعطيلها).'),
 '💳 تعديل أكواد شام كاش':('sham_codes','أرسل نص أكواد شام كاش.'),
 '💳 تعديل أكواد سيريتل كاش':('syriatel_codes','أرسل نص أكواد سيريتل كاش.'),
 '🎁 إدارة الجائزة الحالية':('current_prize','أرسل وصف الجائزة الحالية.'),
 '🎁 إضافة أو حذف البونص':('bonuses','أرسل نص البونصات الجديد.'),
 '📝 تعديل نص البونصات والعروض الحالية':('bonuses','أرسل نص البونصات الجديد.'),
 '🔥 حرق رقم عملية':('burned_operation','أرسل رقم العملية للتسجيل الإداري فقط (لا يؤثر على Ichancy).'),
}

def admin_actions_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text='📋 إدارة المحتوى والروابط',callback_data='ac:content')],
      [InlineKeyboardButton(text='↩️ رجوع للوحة الأدمن',callback_data=BUTTON_IDS['↩️ رجوع للوحة الأدمن'])]])

async def admin_action(message,state,user,action):
    if action in ('content','📝 إدارة المحتوى والروابط'):
        keys=[('شروط الاستخدام','terms'),('الشروحات','tutorials'),('رابط التواصل','contact_url'),('رابط VPN','vpn_url'),('رابط APK','apk_url'),('رابط الألعاب','games_url'),('الدخول المباشر','direct_url'),('الجاكبوت','jackpot'),('اللفة المجانية','free_spin')]
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
    if action=='🎟️ إضافة كود':
        await state.set_state(Input.admin_code)
        return await message.answer('أرسل: CODE المبلغ عدد_الاستخدامات\nمثال: GIFT2026 50 10')
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
    if action=='🎁 إنشاء جائزة ولاء': return await reward_start(message,state)
    if action=='⚡ تعجيل جوائز نقاط الولاء': return await awards(message,state)
    if action=='📢 الإذاعة': return await broadcast_start(message,state)
    if action=='📝 تعديل نص البونصات والعروض الحالية': return await bonus_start(message,state)
    return await message.answer('هذه العملية غير مدعومة دون تكامل رسمي؛ لم يتم تنفيذ أي تغيير مالي خارجي.')

@router.message(Input.admin_config)
async def admin_config_finish(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    data=await state.get_data(); key=data['config_key']; value=(m.text or '').strip()
    if not value or len(value)>3500: return await m.answer('أرسل قيمة نصية لا تتجاوز 3500 حرف.')
    if key in ('dollar_rate','cashback','referral_reward'):
        try:
            v=float(value)
            if v<0 or (key=='cashback' and v>100): raise ValueError()
        except ValueError: return await m.answer('القيمة الرقمية غير صحيحة.')
    with db() as c: c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))
    audit(m.from_user.id,'config_updated',key)
    await state.clear()
    await m.answer('✅ تم حفظ التعديل داخل البوت.',reply_markup=admin_actions_keyboard())

@router.message(Input.admin_code)
async def admin_code_finish(m:Message,state:FSMContext):
    if not admin(m.from_user): return
    try:
        code,amount,uses=(m.text or '').split(); amount=int(amount); uses=int(uses)
        assert 0<amount<=100000000 and 0<uses<=100000 and 1<=len(code)<=40 and code.isascii() and code.isalnum()
    except (ValueError,AssertionError): return await m.answer('مثال: GIFT2026 50 10')
    try:
        with db() as c: c.execute('INSERT INTO gift_codes(code,amount,max_uses) VALUES(?,?,?)',(code.upper(),amount,uses))
    except sqlite3.IntegrityError: return await m.answer('هذا الكود موجود مسبقاً.')
    audit(m.from_user.id,'gift_code_created',code)
    await state.clear()
    await m.answer('✅ تم إنشاء كود هدية للرصيد الداخلي فقط.',reply_markup=keyboard(CODE_ADMIN_ROWS))

async def admin_search_start(m,state):
    await state.set_state(Input.lookup)
    await m.answer('أرسل Telegram ID أو اسم المستخدم للبحث.')

@router.message(Command('cancel'))
async def cancel(m:Message,state:FSMContext):
    await state.clear()
    await m.answer('تم إلغاء العملية. /start للقائمة الرئيسية أو /admin للإدارة.')

@router.message(Command('balance'))
async def my_balance(m:Message):
    save(m.from_user)
    with db() as c: r=c.execute('SELECT bot_balance,points FROM users WHERE id=?',(m.from_user.id,)).fetchone()
    await m.answer(f'💰 رصيد البوت الداخلي: {r["bot_balance"]}\n🌟 نقاط الولاء: {r["points"]}\nرصيد Ichancy منفصل.')

@router.message()
async def fallback(m:Message):
    await m.answer('استخدم أزرار القائمة أو اكتب /start.')

async def main():
    if not TOKEN: raise RuntimeError('Missing BOT_TOKEN')
    logging.basicConfig(level=logging.INFO)
    init()
    bot=Bot(TOKEN)
    dp=Dispatcher()
    dp.include_router(router)
    try: await dp.start_polling(bot)
    finally: await bot.session.close()

if __name__=='__main__': asyncio.run(main())
