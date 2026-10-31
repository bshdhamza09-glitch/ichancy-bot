"""Ichancy official API flows; one-shot financial operations with durable reconciliation."""
import os,re,secrets,sqlite3,asyncio,logging
from decimal import Decimal,InvalidOperation
from aiogram import Router,F
from aiogram.filters import Command
from aiogram.types import Message,CallbackQuery,ReplyKeyboardMarkup,KeyboardButton,ReplyKeyboardRemove,InlineKeyboardMarkup,InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup,State
from ichancy_api import client,IchancyError
router=Router()
class Form(StatesGroup):
    name=State(); account=State(); amount=State()
MENU=['🆕 إنشاء حساب جديد','💳 شحن حساب','💸 سحب من حساب','💰 شحن كامل الرصيد','📤 سحب كامل الرصيد','🎰 ألعاب Ichancy','🌐 دخول إيشانسي','🏠 القائمة الرئيسية']
def kb():
    # Inline controls stay attached to the message, not the Telegram input bar.
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=MENU[i],callback_data=f'ichmenu:{i}'),
         InlineKeyboardButton(text=MENU[i+1],callback_data=f'ichmenu:{i+1}')]
        for i in range(0,len(MENU),2)
    ])
async def show_menu(m,state):
    await state.clear()
    # Remove the old reply keyboard left behind by previous versions.
    await m.answer('تم تحديث لوحة Ichancy.',reply_markup=ReplyKeyboardRemove())
    await m.answer('🟥 خدمات Ichancy — جميع المبالغ بالليرة السورية الجديدة NSP.\nاختر الخدمة من الأزرار أدناه:',reply_markup=kb())
@router.message(Command('cancel','start'))
async def global_commands(m:Message,state:FSMContext):
    await state.clear()
    if (m.text or '').split()[0].lower()=='/start':
        from bot import start
        return await start(m,state)
    await m.answer('✅ تم إلغاء العملية.',reply_markup=kb())
@router.message(F.text=='🏠 القائمة الرئيسية')
async def go_home(m:Message,state:FSMContext):
    await state.clear()
    from bot import home
    await home(m,True)
@router.callback_query(F.data.startswith('ichmenu:'))
async def menu_click(q:CallbackQuery,state:FSMContext):
    try: index=int(q.data.split(':')[1])
    except (ValueError,IndexError):return await q.answer('زر غير صالح',show_alert=True)
    if not 0<=index<len(MENU):return await q.answer('زر غير صالح',show_alert=True)
    await q.answer()
    if index==0:return await begin(q.message,state)
    if 1<=index<=4:return await start_transfer(q.message,state,MODES[MENU[index]])
    if index==5:return await games(q.message)
    if index==6:return await site(q.message)
    await state.clear()
    from bot import home
    await home(q.message,True)
def db():
    from bot import DB
    c=sqlite3.connect(str(DB),timeout=30,isolation_level=None);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000')
    c.execute('CREATE TABLE IF NOT EXISTS ichancy_accounts (telegram_id INTEGER NOT NULL, login TEXT NOT NULL UNIQUE, player_id TEXT, PRIMARY KEY(telegram_id,login))')
    c.execute("CREATE TABLE IF NOT EXISTS ichancy_operations (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL, login TEXT NOT NULL, player_id TEXT NOT NULL, kind TEXT NOT NULL, amount INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    return c
async def say_menu(m,state):
    await show_menu(m,state)
@router.message(F.text=='🟥 Ichancy')
async def menu(m:Message,state:FSMContext):await say_menu(m,state)
@router.callback_query(F.data=='ichancy_menu')
async def inline_menu(q:CallbackQuery,state:FSMContext):
    await q.answer();await say_menu(q.message,state)
@router.message(F.text=='🆕 إنشاء حساب جديد')
async def begin(m:Message,state:FSMContext):
    await state.clear();await state.set_state(Form.name);await m.answer('أدخل اسم حساب Ichancy المطلوب (إنكليزي وأرقام):\nللإلغاء اضغط الزر أدناه.',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='❌ إلغاء',callback_data='ichancy_menu')]]))
@router.message(Form.name)
async def register(m:Message,state:FSMContext):
    name=(m.text or '').strip().lower()
    if name.startswith('/') or name in [x.lower() for x in MENU]:
        return await m.answer('استخدم /cancel للإلغاء أو اختر خدمة من القائمة.',reply_markup=kb())
    if not re.fullmatch('[a-z][a-z0-9_]{2,18}',name):return await m.answer('الاسم لازم يبدأ بحرف إنكليزي، من 3 إلى 19 حرفاً/رقماً.')
    login=f'{name}_{secrets.randbelow(900000)+100000}';email=f'{login}@saw.com';password=secrets.token_urlsafe(16)+'A1!'
    progress=await m.answer('⏳ جاري إنشاء الحساب...')
    try:
        result=await asyncio.wait_for(client.register(login,email,password),timeout=65)
        if str(result)!='1':raise IchancyError('لم يتم تأكيد إنشاء الحساب من الخادم')
        with db() as c:c.execute('INSERT INTO ichancy_accounts(telegram_id,login) VALUES(?,?)',(m.from_user.id,login))
        await progress.edit_text(f'✅ تم إنشاء الحساب\nالدخول: {login}\nالإيميل: {email}\nكلمة السر: {password}\nاحفظ كلمة السر بمكان آمن.',reply_markup=kb())
    except (IchancyError,sqlite3.Error,asyncio.TimeoutError) as e:
        await progress.edit_text(f'⚠️ لم يتم تأكيد إنشاء الحساب: {e}\nإذا وصل الطلب إلى registerPlayer، تحقّق من وجود الحساب قبل إعادة المحاولة.',reply_markup=kb())
    except Exception:
        logging.exception('Ichancy registration unexpected failure')
        await progress.edit_text('❌ حدث خطأ تقني أثناء إنشاء الحساب. لم يتم تأكيد العملية. راجع سجلات Railway قبل إعادة المحاولة.',reply_markup=kb())
    finally:await state.clear()
MODES={'💳 شحن حساب':'deposit','💸 سحب من حساب':'withdraw','💰 شحن كامل الرصيد':'deposit_all','📤 سحب كامل الرصيد':'withdraw_all'}
@router.message(F.text.in_(set(MODES)))
async def start_transfer(m,state,mode):
    await state.clear();await state.update_data(mode=mode);await state.set_state(Form.account)
    await m.answer('أرسل اسم حساب Ichancy (login) الذي تريد التعامل معه:',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='❌ إلغاء',callback_data='ichancy_menu')]]))
async def transfer_start(m:Message,state:FSMContext):
    await start_transfer(m,state,MODES[m.text])
@router.message(Form.account)
async def account(m:Message,state:FSMContext):
    login=(m.text or '').strip()
    if login.startswith('/') or login in MENU:return await m.answer('اضغط إلغاء أو أرسل اسم الحساب.',reply_markup=kb())
    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]{2,40}',login):return await m.answer('أدخل اسم حساب صحيح.')
    d=await state.get_data();mode=d['mode']
    try:
        players=await client.players(login)
        players=[p for p in players if str(p.get('username','')).lower()==login.lower()]
        if len(players)!=1:raise IchancyError('الحساب غير موجود أو غير مطابق تماماً.')
        pid=str(players[0]['playerId'])
        if mode.startswith('withdraw'):
            with db() as c:
                own=c.execute('SELECT player_id FROM ichancy_accounts WHERE telegram_id=? AND login=?',(m.from_user.id,login)).fetchone()
                if not own:raise IchancyError('السحب مسموح فقط للحساب الذي أنشأته من خلال بوتك. الحسابات القديمة تحتاج تحقق ملكية منفصل.')
                if own['player_id'] and own['player_id']!=pid:raise IchancyError('تغير معرّف اللاعب؛ العملية موقوفة.')
        with db() as c:c.execute('UPDATE ichancy_accounts SET player_id=? WHERE telegram_id=? AND login=?',(pid,m.from_user.id,login))
        await state.update_data(login=login,pid=pid)
        if mode.endswith('_all'):
            if mode=='deposit_all':
                from bot import balance_of
                amount=balance_of(m.from_user.id)
            else:
                amount=await client.balance(pid)
            await preview(m,state,amount)
        else:
            await state.set_state(Form.amount);await m.answer('أرسل المبلغ بالليرة السورية الجديدة NSP (عدد صحيح موجب):')
    except (IchancyError,KeyError,sqlite3.Error) as e:await m.answer(f'❌ {e}',reply_markup=kb());await state.clear()
@router.message(Form.amount)
async def amount_input(m:Message,state:FSMContext):await preview(m,state,(m.text or '').strip())
async def preview(m,state,amount):
    try:
        a=Decimal(str(amount))
        if not a.is_finite() or a!=a.to_integral_value() or a<=0 or a>1000000000:raise ValueError()
        a=int(a)
    except (InvalidOperation,ValueError,TypeError):return await m.answer('❌ المبلغ لازم يكون عدد صحيح موجب وأقل من مليار NSP.')
    d=await state.get_data();mode=d['mode'];kind='deposit' if mode.startswith('deposit') else 'withdraw'
    if kind=='deposit':
        from bot import balance_of
        if balance_of(m.from_user.id)<a:return await m.answer('❌ رصيد البوت غير كافٍ.')
    else:
        try:
            b=await client.balance(d['pid'])
            if b is None or Decimal(str(b))<a:return await m.answer('❌ رصيد Ichancy غير كافٍ أو غير متاح.')
        except IchancyError as e:return await m.answer(f'❌ {e}')
    await state.clear()
    # Single-use confirmation token stored server-side, not an amount supplied by callback.
    with db() as c:
        c.execute('INSERT INTO ichancy_operations(telegram_id,login,player_id,kind,amount,status) VALUES(?,?,?,?,?,?)',(m.from_user.id,d['login'],d['pid'],kind,a,'awaiting_confirmation'))
        op=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    label='شحن' if kind=='deposit' else 'سحب'
    await m.answer(f'تأكيد {label} {a:,} NSP\nالحساب: {d["login"]}\nلن تُنفّذ العملية قبل الضغط على تأكيد.',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ تأكيد العملية',callback_data=f'ichop:yes:{op}'),InlineKeyboardButton(text='❌ إلغاء',callback_data=f'ichop:no:{op}')]]))
@router.callback_query(F.data.startswith('ichop:'))
async def confirm(q:CallbackQuery):
    try:_,choice,opid=q.data.split(':');opid=int(opid)
    except (ValueError,AttributeError):return await q.answer('طلب غير صالح',show_alert=True)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        op=c.execute('SELECT * FROM ichancy_operations WHERE id=? AND telegram_id=?',(opid,q.from_user.id)).fetchone()
        if not op or op['status']!='awaiting_confirmation':
            c.rollback();return await q.answer('تم التعامل مع هذا الطلب سابقاً',show_alert=True)
        if choice=='no':
            c.execute("UPDATE ichancy_operations SET status='cancelled' WHERE id=?",(opid,));c.commit();await q.answer('تم الإلغاء');return await q.message.answer('تم إلغاء العملية.',reply_markup=kb())
        if choice!='yes':c.rollback();return await q.answer('طلب غير صالح')
        if op['kind']=='deposit':
            row=c.execute('SELECT bot_balance FROM users WHERE id=?',(q.from_user.id,)).fetchone()
            if not row or row['bot_balance']<op['amount']:
                c.rollback();return await q.answer('رصيد البوت غير كافٍ',show_alert=True)
            c.execute('UPDATE users SET bot_balance=bot_balance-? WHERE id=?',(op['amount'],q.from_user.id))
        c.execute("UPDATE ichancy_operations SET status='sending',updated_at=CURRENT_TIMESTAMP WHERE id=?",(opid,));c.commit()
    await q.answer('جاري تنفيذ العملية')
    # Never retry financial requests, including after timeouts. 'sending' survives process restarts.
    try:
        result=await client.transfer(op['player_id'],op['amount'],op['kind']=='deposit',f'Telegram {q.from_user.id} operation {opid}')
        if not isinstance(result,dict) or result.get('currencyCode')!='NSP':raise IchancyError('النتيجة غير مؤكدة؛ تحتاج مراجعة يدوية')
    except IchancyError as e:
        with db() as c:c.execute("UPDATE ichancy_operations SET status='needs_review',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='sending'",(opid,))
        await q.message.answer(f'⚠️ العملية #{opid} بحاجة مراجعة إدارية، ولا يجوز تكرارها.\n{e}')
        return
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        if op['kind']=='withdraw':
            c.execute('UPDATE users SET bot_balance=bot_balance+? WHERE id=?',(op['amount'],q.from_user.id))
        c.execute("UPDATE ichancy_operations SET status='completed',updated_at=CURRENT_TIMESTAMP WHERE id=?",(opid,));c.commit()
    await q.message.answer(f'✅ تمت العملية #{opid} بمبلغ {op["amount"]:,} NSP.',reply_markup=kb())
@router.message(F.text=='🎰 ألعاب Ichancy')
async def games(m:Message):await m.answer('🎰 ألعاب Ichancy: https://ichancy.com',reply_markup=kb())
@router.message(F.text=='🌐 دخول إيشانسي')
async def site(m:Message):await m.answer('🌐 الدخول: https://ichancy.com',reply_markup=kb())
@router.message(Command('ichancy_balance'))
async def balance(m:Message):
    parts=(m.text or '').split(maxsplit=1)
    if len(parts)<2:return await m.answer('اكتب /ichancy_balance username')
    try:
        ps=await client.players(parts[1].strip());ps=[p for p in ps if str(p.get('username','')).lower()==parts[1].strip().lower()]
        if len(ps)!=1:return await m.answer('لم يتم العثور على حساب واحد مطابق.')
        b=await client.balance(ps[0]['playerId']);await m.answer(f'رصيد {ps[0]["username"]}: {b} NSP')
    except (IchancyError,KeyError) as e:await m.answer(f'تعذر الاستعلام: {e}')

@router.message(Command('ichancy_review'))
async def review_list(m:Message):
    from bot import ADMIN_IDS
    if m.from_user.id not in ADMIN_IDS:return
    with db() as c:rows=c.execute("SELECT id,telegram_id,login,kind,amount,status FROM ichancy_operations WHERE status IN ('sending','needs_review') ORDER BY id DESC LIMIT 20").fetchall()
    await m.answer('\n'.join(f'#{r["id"]} | {r["telegram_id"]} | {r["login"]} | {r["kind"]} | {r["amount"]} NSP | {r["status"]}' for r in rows) or 'لا توجد عمليات معلقة.')
@router.message(Command('ichancy_resolve'))
async def review_resolve(m:Message):
    from bot import ADMIN_IDS
    if m.from_user.id not in ADMIN_IDS:return
    parts=(m.text or '').split()
    if len(parts)!=3 or not parts[1].isdigit() or parts[2] not in ('completed','not_executed'):
        return await m.answer('بعد التحقق من سجل Ichancy يدوياً: /ichancy_resolve ID completed أو /ichancy_resolve ID not_executed')
    opid=int(parts[1]);decision=parts[2]
    with db() as c:
        c.execute('BEGIN IMMEDIATE');op=c.execute('SELECT * FROM ichancy_operations WHERE id=?',(opid,)).fetchone()
        if not op or op['status'] not in ('sending','needs_review'):
            c.rollback();return await m.answer('العملية غير موجودة أو سبق حسمها.')
        if op['kind']=='deposit' and decision=='not_executed':
            c.execute('UPDATE users SET bot_balance=bot_balance+? WHERE id=?',(op['amount'],op['telegram_id']))
        if op['kind']=='withdraw' and decision=='completed':
            c.execute('UPDATE users SET bot_balance=bot_balance+? WHERE id=?',(op['amount'],op['telegram_id']))
        c.execute('UPDATE ichancy_operations SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',('completed' if decision=='completed' else 'not_executed',opid));c.commit()
    await m.answer(f'تم حسم العملية #{opid} بعد مراجعتك لسجل Ichancy.')
    try:await m.bot.send_message(op['telegram_id'],f'تمت مراجعة العملية #{opid}: {"مكتملة" if decision=="completed" else "لم تنفذ"}.')
    except Exception:pass
