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
from aiogram.types import (FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, Message, ReplyKeyboardMarkup)
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
    ['👥 المستخدمين'], ['🔎 البحث عن مستخدم'], ['📊 تقرير'],
    ['🎟️ إضافة كود'], ['📜 سجل مستخدم'], ['💰 توزيع أرباح الإحالات'],
    ['➕ إضافة رصيد', '➖ خصم رصيد'],
    ['📝 تعديل نص البونصات والعروض الحالية'], ['🎁 إضافة أو حذف البونص'],
    ['📢 الإذاعة'], ['💳 تعديل أكواد شام كاش', '💳 تعديل أكواد سيريتل كاش'],
    ['⚙️ حالة البوت (تشغيل/إيقاف)'], ['⚙️ تعديل سعر الدولار'],
    ['🔥 حرق رقم عملية'], ['💸 الكاش باك الأسبوعي 10%'],
    ['🎁 إدارة الجائزة الحالية'], ['🚫 حظر مستخدم', '🔓 فك حظر مستخدم'],
    ['🌟 إدارة نقاط الولاء'], ['⚡ تعجيل جوائز نقاط الولاء'],
    ['🏠 القائمة الرئيسية'],
]
ALL = {x for row in ROWS for x in row}
ADMIN_ALL = {x for row in ADMIN_ROWS for x in row}

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

def db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    return con

def init():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, referrer INTEGER, points INTEGER NOT NULL DEFAULT 0, banned INTEGER NOT NULL DEFAULT 0, joined TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS rewards(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, cost INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS claims(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, reward_id INTEGER NOT NULL, points_cost INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created TEXT DEFAULT CURRENT_TIMESTAMP, resolved TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, actor INTEGER, action TEXT, details TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        c.execute("INSERT OR IGNORE INTO settings VALUES ('enabled','1')")
        c.execute("INSERT OR IGNORE INTO settings VALUES ('bonuses','لا توجد عروض منشورة حالياً.')")

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

def keyboard(rows):
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x) for x in row] for row in rows], resize_keyboard=True, is_persistent=True, input_field_placeholder='اختر خدمة من القائمة')

def back():
    return keyboard([['🏠 القائمة الرئيسية'],['👮 لوحة تحكم الإدارة']])

def admin(u):
    return u and u.id in ADMIN_IDS

async def home(m, welcome=False):
    msg=f'🏠 أهلاً بك في بوت {NAME}\nاختر الخدمة من القائمة التالية 👇'
    if welcome and GIF.exists():
        await m.answer_animation(FSInputFile(GIF), caption=msg)
    else:
        await m.answer(msg, reply_markup=keyboard(ROWS + ([['👮 لوحة تحكم الإدارة']] if admin(m.from_user) else [])))
    if welcome and GIF.exists():
        await m.answer('📋 القائمة الرئيسية',reply_markup=keyboard(ROWS + ([['👮 لوحة تحكم الإدارة']] if admin(m.from_user) else [])))

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
    await m.answer(f'تم تسجيل طلب الجائزة #{cid} وهو بانتظار مراجعة الأدمن.',reply_markup=keyboard(ROWS + ([['👮 لوحة تحكم الإدارة']] if admin(m.from_user) else [])))
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
    await m.answer(f'🌟 إدارة الولاء\nطلبات معلّقة: {pending}\n{txt}',reply_markup=keyboard([['➕ منح نقاط ولاء'],['🎁 إنشاء جائزة ولاء'],['⚡ تعجيل جوائز نقاط الولاء'],['👮 لوحة تحكم الإدارة']]))

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
    await m.answer(f'تمت إضافة {pts} نقطة للمستخدم {uid}.',reply_markup=keyboard(ADMIN_ROWS))

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
    await m.answer(f'تم إنشاء الجائزة #{rid}: {title} مقابل {cost} نقطة.',reply_markup=keyboard(ADMIN_ROWS))

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
    await m.answer(f'تم تحديث الطلب #{cid} إلى {status}.',reply_markup=keyboard(ADMIN_ROWS))
    try: await m.bot.send_message(r['user_id'],f'تحديث طلب جائزة الولاء #{cid}: {status}')
    except Exception: logging.exception('Notification failed')

@router.message(F.text == '👥 المستخدمين')
async def users(m:Message):
    if not admin(m.from_user): return
    with db() as c:
        total=c.execute('SELECT COUNT(*) n FROM users').fetchone()['n']
        banned=c.execute('SELECT COUNT(*) n FROM users WHERE banned=1').fetchone()['n']
    await m.answer(f'👥 عدد المستخدمين: {total}\n🚫 المحظورون: {banned}',reply_markup=keyboard(ADMIN_ROWS))

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
    await m.answer('أرسل Telegram ID للمستخدم.',reply_markup=back())

@router.message(Input.lookup)
async def lookup_finish(m:Message,state:FSMContext):
    if not (m.text or '').isdigit(): return await m.answer('أرسل رقماً صحيحاً.')
    with db() as c:
        u=c.execute('SELECT * FROM users WHERE id=?',(int(m.text),)).fetchone()
    await state.clear()
    await m.answer(f"المستخدم: {u['id']}\n@{u['username']}\nنقاط: {u['points']}\nمحظور: {bool(u['banned'])}" if u else 'المستخدم غير موجود.',reply_markup=keyboard(ADMIN_ROWS))

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
    await m.answer('تم تحديث حالة المستخدم.',reply_markup=keyboard(ADMIN_ROWS))

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
    if m.text=='🟥 Ichancy': return await m.answer(f'مرحباً بك في {NAME}.')
    if m.text in ('💸 شحن رصيد البوت','💰 سحب رصيد البوت','🎟️ إهداء رصيد'):
        return await m.answer('🔒 الخدمة غير مفعلة. لا يتم تنفيذ أي تحويل مالي قبل ربط الـ API الرسمي واختباره.')
    await m.answer(f'{m.text}\n\nهذا القسم قيد الإعداد. لا توجد عملية تلقائية مفعّلة حالياً.')

@router.message(F.text.in_(ADMIN_ALL))
async def admin_placeholder(m:Message):
    if not admin(m.from_user): return
    await m.answer(f'{m.text}\n\n🛠️ هذا القسم ظاهر حسب التصميم المرجعي، لكنه غير مفعّل بعد. لا تتم أي حركة مالية أو سحب بيانات غير مصرح به.')

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
