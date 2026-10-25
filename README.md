# Sheikh Telegram Bot — Railway

بوت تلغرام بأزرار Inline داخل رسالة الترحيب بدلاً من لوحة المفاتيح السفلية.

## تشغيل Railway
1. ارفع محتويات هذا المجلد إلى جذر مستودع GitHub خاص (أو اضبط Root Directory إن كان المجلد فرعياً).
2. Railway → New Project → Deploy from GitHub Repo.
3. Variables: `BOT_TOKEN` (سري) و `BOT_NAME=Sheikh`.
4. Start Command: `python bot.py` (موجود أيضاً في railway.json).
5. أرسل `/start` للبوت. إن كانت هناك لوحة مفاتيح قديمة فستختفي عند `/start`.

ملاحظة: اسم حساب البوت الظاهر أعلى محادثة تلغرام يُعدّل من BotFather وليس من كود Python. وGIF الترحيب القديم لا يزال موجوداً؛ استبدله إن أردت شعار Sheikh بدلاً من الرسوم السابقة.

الأزرار المالية تجريبية ومقفلة. لا توجد أي عمليات مالية حقيقية ولا اتصال API. SQLite محلي وغير دائم على Railway بدون Volume؛ انتقل إلى قاعدة بيانات دائمة قبل الاستخدام الفعلي.
