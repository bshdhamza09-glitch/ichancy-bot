"""Ichancy menu and account registration, using documented API only."""
import os,re,secrets,sqlite3
from aiogram import Router,F
from aiogram.filters import Command
from aiogram.types import Message,CallbackQuery,ReplyKeyboardMarkup,KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup,State
from ichancy_api import client,IchancyError
router=Router()
class Form(StatesGroup): name=State(); lookup=State()
MENU=['🆕 إنشاء حساب جديد','💳 شحن حساب','💸 سحب من حساب','💰 شحن كامل الرصيد','📤 سحب كامل الرصيد','🎰 ألعاب Ichancy','🌐 دخول إيشانسي','🏠 القائمة الرئيسية']
def kb():return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x) for x in MENU[i:i+2]] for i in range(0,len(MENU),2)],resize_keyboard=True)
@router.message(F.text=='🟥 Ichancy')
async def menu(m:Message,state:FSMContext):
    await state.clear();await m.answer('🟥 خدمات Ichancy\nجميع المبالغ بالليرة السورية الجديدة NSP.',reply_markup=kb())
@router.callback_query(F.data=='ichancy_menu')
async def inline_menu(q:CallbackQuery,state:FSMContext):
    await q.answer();await menu(q.message.model_copy(update={'from_user':q.from_user}),state)
@router.message(F.text=='🆕 إنشاء حساب جديد')
async def begin(m:Message,state:FSMContext):
    await state.set_state(Form.name);await m.answer('أدخل اسم حساب Ichancy المطلوب (أحرف إنكليزية وأرقام فقط):')
@router.message(Form.name)
async def register(m:Message,state:FSMContext):
    name=(m.text or '').strip().lower()
    if not re.fullmatch('[a-z][a-z0-9_]{2,18}',name):return await m.answer('الاسم لازم يبدأ بحرف إنكليزي، وطوله من 3 إلى 19 حرفاً/رقماً.')
    login=f'{name}_{secrets.randbelow(900000)+100000}'
    email=f'{login}@saw.com';password=secrets.token_urlsafe(14)+'A1!'
    await m.answer('⏳ جاري إنشاء الحساب عبر API الرسمي...')
    try:
        result=await client.register(login,email,password)
        if result != 1:raise IchancyError('الاستجابة غير مؤكدة؛ لم نعتبر الحساب منشأً')
        await state.clear()
        await m.answer(f'✅ تم إنشاء الحساب\nالدخول: {login}\nالإيميل: {email}\nكلمة السر: {password}\nاحتفظ بها بمكان آمن.',reply_markup=kb())
    except IchancyError as e:
        await state.clear();await m.answer(f'❌ لم يتأكد إنشاء الحساب: {e}',reply_markup=kb())
@router.message(F.text.in_({'💳 شحن حساب','💸 سحب من حساب','💰 شحن كامل الرصيد','📤 سحب كامل الرصيد'}))
async def transfer_start(m:Message,state:FSMContext):
    await state.clear()
    await m.answer('⚠️ عمليات التحويل المالي الآلي غير مفعلة في هذه النسخة لحماية الأرصدة من الخصم المكرر.\nيمكن للإدارة اختبار API الرسمي بعد ضبط إعدادات Railway، ثم تفعيل التسوية المالية الآمنة. لا يوجد أي تحويل منفذ الآن.',reply_markup=kb())
@router.message(F.text=='🎰 ألعاب Ichancy')
async def games(m:Message):await m.answer('🎰 ألعاب Ichancy: https://ichancy.com',reply_markup=kb())
@router.message(F.text=='🌐 دخول إيشانسي')
async def site(m:Message):await m.answer('🌐 الدخول: https://ichancy.com',reply_markup=kb())
@router.message(Command('ichancy_balance'))
async def balance(m:Message):
    parts=(m.text or '').split(maxsplit=1)
    if len(parts)<2:return await m.answer('اكتب /ichancy_balance username')
    try:
        players=await client.players(parts[1].strip())
        if len(players)!=1:return await m.answer('لم يتم العثور على حساب واحد مطابق.')
        p=players[0];bal=await client.balance(p['playerId']);await m.answer(f'رصيد {p.get("username",parts[1])}: {bal} NSP')
    except (IchancyError,KeyError) as e:await m.answer(f'تعذر الاستعلام: {e}')
