"""Official documented Ichancy Agent API client. No legacy endpoints."""
import asyncio, json, os, time, secrets
from pathlib import Path
import aiohttp

BASE=os.getenv("ICHANCY_API_BASE_URL", "https://agents.ichancy.com").rstrip("/")
USER=os.getenv("ICHANCY_CASHIER_USERNAME", "")
PASSWORD=os.getenv("ICHANCY_CASHIER_PASSWORD", "")
AGENT=os.getenv("ICHANCY_AGENT_ID", "")
TOKEN_FILE=Path(os.getenv("ICHANCY_TOKEN_PATH", "/tmp/ichancy_agent_tokens.json"))
class IchancyError(Exception): pass
class Client:
    def __init__(self):
        self.lock=asyncio.Lock();self.access=None;self.refresh=None;self.expires=0
        try:
            d=json.loads(TOKEN_FILE.read_text());self.access=d['access'];self.refresh=d['refresh'];self.expires=d['expires']
        except (OSError,KeyError,ValueError):pass
    def persist(self):
        TOKEN_FILE.parent.mkdir(parents=True,exist_ok=True)
        tmp=TOKEN_FILE.with_suffix('.tmp');tmp.write_text(json.dumps(dict(access=self.access,refresh=self.refresh,expires=self.expires)));tmp.chmod(0o600);tmp.replace(TOKEN_FILE)
    async def raw(self,endpoint,data,token=None):
        if not BASE.startswith('https://'):raise IchancyError('ICHANCY_API_BASE_URL must be HTTPS')
        headers={'Accept':'application/json','Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        timeout=aiohttp.ClientTimeout(total=20)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.post(BASE+'/global/api/UserApi/'+endpoint,json=data,headers=headers) as r:
                    body=await r.json(content_type=None)
                    if not isinstance(body,dict):raise IchancyError('استجابة غير مفهومة من الخادم')
                    if r.status>=400 or body.get('status') is False or body.get('result') is False or body.get('result') is None:
                        msg='; '.join(str(n.get('content','')) for n in body.get('notification',[]) if isinstance(n,dict))
                        raise IchancyError(msg or 'رفض الخادم الطلب')
                    return body.get('result')
        except (aiohttp.ClientError,asyncio.TimeoutError) as e:raise IchancyError('تعذر تأكيد العملية من الخادم؛ لا تعيد إرسال طلب مالي تلقائياً') from e
    async def auth(self,force=False):
        async with self.lock:
            if self.access and self.expires>time.time()+60 and not force:return self.access
            if self.refresh:
                try:d=await self.raw('refreshToken',{'refreshToken':self.refresh})
                except IchancyError:d=None
                if isinstance(d,dict) and d.get('accessToken') and d.get('refreshToken'):
                    self.access=d['accessToken'];self.refresh=d['refreshToken'];self.expires=time.time()+3500;self.persist();return self.access
            if not USER or not PASSWORD:raise IchancyError('أضف بيانات الكاشير في Railway')
            d=await self.raw('signin',{'username':USER,'password':PASSWORD})
            if not isinstance(d,dict) or not d.get('accessToken'):raise IchancyError('فشل تسجيل الدخول')
            self.access=d['accessToken'];self.refresh=d['refreshToken'];self.expires=time.time()+3500;self.persist();return self.access
    async def call(self,endpoint,payload):
        token=await self.auth()
        try:return await self.raw(endpoint,payload,token)
        except IchancyError as e:
            # Never retry mutations: a timeout or ambiguous response could already have executed.
            if endpoint in ('depositToPlayer','withdrawFromPlayer','registerPlayer'):raise
            if 'unauthorized' in str(e).lower() or 'token' in str(e).lower():
                return await self.raw(endpoint,payload,await self.auth(force=True))
            raise
    async def players(self,login):
        d=await self.call('getPlayersForCurrentAgent',{'start':0,'limit':20,'filter':{'userName':{'action':'=','value':login,'valueLabel':login}}})
        return d.get('records',[]) if isinstance(d,dict) else []
    async def register(self,login,email,password):
        if not AGENT:raise IchancyError('ICHANCY_AGENT_ID غير مضبوط؛ مطلوب رسمياً لإنشاء الحساب')
        return await self.call('registerPlayer',{'player':{'email':email,'password':password,'parentId':AGENT,'login':login}})
    async def balance(self,pid):
        d=await self.call('getPlayerBalanceById',{'playerId':str(pid)})
        return next((x.get('balance') for x in d if x.get('currencyCode')=='NSP'),None) if isinstance(d,list) else None
    async def transfer(self,pid,amount,deposit,comment):
        from decimal import Decimal
        a=Decimal(str(amount));
        if not a.is_finite() or a<=0:raise IchancyError('المبلغ غير صالح')
        payload={'amount':float(a if deposit else -a),'comment':comment,'playerId':str(pid),'currencyCode':'NSP','currency':'NSP','moneyStatus':5}
        return await self.call('depositToPlayer' if deposit else 'withdrawFromPlayer',payload)
client=Client()
