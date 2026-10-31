"""Ichancy documented Agent API: authentication, token rotation and no blind retries."""
import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path

import aiohttp

BASE = os.getenv('ICHANCY_API_BASE_URL', 'https://agents.ichancy.com').rstrip('/')
USER = os.getenv('ICHANCY_CASHIER_USERNAME', '').strip()
PASSWORD = os.getenv('ICHANCY_CASHIER_PASSWORD', '')
AGENT = os.getenv('ICHANCY_AGENT_ID', '').strip()

# Keep the token pair on the same mounted volume as the bot DB, when configured.
# Railway requires a persistent volume mounted at /data for this to survive redeploys.
_default_db = Path(os.getenv('DATABASE_PATH', str(Path(__file__).with_name('sheikh.db'))))
TOKEN_FILE = Path(os.getenv('ICHANCY_TOKEN_PATH', str(_default_db.with_name('ichancy_agent_tokens.json'))))
_IDENTITY = hashlib.sha256((BASE + '\n' + USER.lower()).encode()).hexdigest()


class IchancyError(Exception):
    """Safe, user-presentable API error (never includes credentials)."""


class IchancyAuthExpired(IchancyError):
    """Documented invalid or expired API access/refresh token."""


class IchancyForbidden(IchancyError):
    """HTTP 403 HTML / Cloudflare policy prevents official API access."""


class Client:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.access = None
        self.refresh = None
        self.expires = 0
        self.refresh_expires = 0
        self._load()

    def _load(self):
        try:
            d = json.loads(TOKEN_FILE.read_text(encoding='utf-8'))
            if d.get('identity') != _IDENTITY:
                return  # tokens belong to another host or agent username
            self.access = d.get('access') or None
            self.refresh = d.get('refresh') or None
            self.expires = float(d.get('expires') or 0)
            self.refresh_expires = float(d.get('refresh_expires') or 0)
        except (OSError, ValueError, TypeError):
            return

    def persist(self):
        try:
            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = TOKEN_FILE.with_name(TOKEN_FILE.name + '.tmp')
            import os as _os
            fd = _os.open(str(tmp), _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC, 0o600)
            try:
                with _os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump({'identity': _IDENTITY, 'access': self.access,
                               'refresh': self.refresh, 'expires': self.expires,
                               'refresh_expires': self.refresh_expires}, f)
                    f.flush()
                    _os.fsync(f.fileno())
            except Exception:
                try: tmp.unlink(missing_ok=True)
                except OSError: pass
                raise
            tmp.replace(TOKEN_FILE)
        except OSError:
            logging.exception('Ichancy token persistence unavailable; configure ICHANCY_TOKEN_PATH on persistent volume')
            # Do not silently lose a just-issued refresh token during rotation.
            raise IchancyError('فشل حفظ جلسة Ichancy بأمان؛ تحقق من DATABASE_PATH وحجم Railway')

    def _set_tokens(self, result):
        if not isinstance(result, dict) or not result.get('accessToken') or not result.get('refreshToken'):
            raise IchancyError('فشل التحقق من زوج التوكنات الذي أعاده الخادم')
        self.access = result['accessToken']
        self.refresh = result['refreshToken']
        self.expires = time.time() + 3500  # 1-hour TTL less safety margin
        self.refresh_expires = time.time() + 7 * 86400 - 120
        self.persist()
        return self.access

    async def raw(self, endpoint, data, token=None):
        if not BASE.startswith('https://'):
            raise IchancyError('ICHANCY_API_BASE_URL يجب أن يبدأ بـ HTTPS')
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json',
                   'User-Agent': 'EL-SHEIKH-Official-AgentAPI/1.1'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        timeout = aiohttp.ClientTimeout(total=20, connect=8)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(BASE + '/global/api/UserApi/' + endpoint,
                                        json=data, headers=headers, allow_redirects=False) as response:
                    status = response.status
                    content_type = response.headers.get('Content-Type', '')
                    ray = response.headers.get('CF-Ray', '')[:60]
                    if status in (301, 302, 303, 307, 308):
                        raise IchancyError(f'API يعيد HTTP {status} عند {endpoint}؛ تحقق من عنوان الخادم')
                    if 'json' not in content_type.lower():
                        if status == 403:
                            # A CF-Ray header alone does not prove a Cloudflare WAF block:
                            # the origin can send 403 through Cloudflare as well.
                            sample = (await response.content.read(2048)).decode('utf-8', errors='replace').lower()
                            challenged = (response.headers.get('cf-mitigated', '').lower() == 'challenge'
                                          or 'challenge-platform' in sample
                                          or 'just a moment' in sample
                                          or 'attention required' in sample)
                            origin = 'Cloudflare challenge' if challenged else 'server/origin or Cloudflare rule'
                            logging.warning('Ichancy HTTP 403 endpoint=%s source=%s cf_ray=%s',
                                            endpoint, origin, ray or '-')
                            raise IchancyForbidden(f'Ichancy يرفض الاتصال HTTP 403 عند {endpoint}'
                                + (f' (CF-Ray: {ray})' if ray else '')
                                + ('؛ يوجد تحدي Cloudflare للطلبات غير التفاعلية.' if challenged else
                                   '؛ غير معروف إن كان الرفض من Cloudflare أم من الخادم الأصلي.')
                                + ' تجديد التوكن لا يحل رفض signin قبل إصدار توكن.')
                        raise IchancyError(f'Ichancy رد HTTP {status} ليس JSON عند {endpoint} ({content_type[:65]})')
                    try:
                        body = await response.json(content_type=None)
                    except (ValueError, UnicodeError) as ex:
                        raise IchancyError(f'استجابة JSON غير صالحة عند {endpoint} (HTTP {status})') from ex
                    if not isinstance(body, dict):
                        raise IchancyError(f'استجابة غير مفهومة عند {endpoint}')
                    notices = body.get('notification') or []
                    detail = '; '.join(str(x.get('content', ''))[:140] for x in notices if isinstance(x, dict))[:260]
                    result = body.get('result')
                    # The official 2026 documentation shows HTTP 201 + result='ex'
                    # for an expired access token, not only HTTP 401.
                    # Distinguish that from HTTP 201 sign-in errors, which are NOT
                    # evidence an access token expired.
                    expired_access = (endpoint not in ('signin', 'refreshToken') and
                                      (status in (201, 401) and
                                       (result == 'ex' or status == 401)))
                    expired_refresh = (endpoint == 'refreshToken' and
                                       (status == 401 or any(t in detail.lower() for t in (
                                           'expired refresh token', 'invalid refresh token'))))
                    if expired_access or expired_refresh:
                        raise IchancyAuthExpired(f'جلسة Ichancy منتهية عند {endpoint} (HTTP {status})')
                    if status >= 400 or body.get('status') is False or result is False or result is None:
                        raise IchancyError(f'{endpoint}: HTTP {status}: {detail or "رفض الخادم الطلب"}')
                    return result
        except asyncio.TimeoutError as ex:
            raise IchancyError(f'انتهت مهلة الاتصال (20 ثانية) عند {endpoint}؛ حالة العملية غير مؤكدة') from ex
        except aiohttp.ClientConnectorCertificateError as ex:
            raise IchancyError(f'خطأ شهادة HTTPS عند {endpoint}') from ex
        except aiohttp.ClientConnectorError as ex:
            raise IchancyError(f'تعذر اتصال API عند {endpoint}؛ تحقق من الاستضافة والرابط') from ex
        except aiohttp.ClientError as ex:
            raise IchancyError(f'انقطع اتصال API عند {endpoint} ({type(ex).__name__})؛ لا تكرر عملية مالية') from ex

    async def auth(self, force=False):
        async with self.lock:
            if not force and self.access and self.expires > time.time() + 60:
                return self.access
            if self.refresh and self.refresh_expires > time.time() + 60:
                try:
                    result = await self.raw('refreshToken', {'refreshToken': self.refresh})
                except IchancyAuthExpired:
                    # Only a definite invalid refresh permits a fresh signin.
                    self.refresh = None
                    self.access = None
                else:
                    if isinstance(result, dict) and result.get('accessToken') and result.get('refreshToken'):
                        return self._set_tokens(result)
                    # Expected malformed/invalid refresh response; signin is now appropriate.
                    if isinstance(result, (list, bool)):
                        self.refresh = None
                        self.access = None
                    else:
                        raise IchancyError('استجابة refreshToken غير واضحة، لن نلغي الجلسة ونعيد signin عشوائياً')
            if not USER or not PASSWORD:
                raise IchancyError('أضف بيانات الكاشير في Railway')
            return self._set_tokens(await self.raw('signin', {'username': USER, 'password': PASSWORD}))

    async def call(self, endpoint, payload):
        token = await self.auth()
        try:
            return await self.raw(endpoint, payload, token)
        except IchancyAuthExpired:
            # Retry read-only endpoints only. Mutations are never replayed.
            if endpoint not in ('getAgentAllWallets', 'getPlayersForCurrentAgent', 'getPlayerBalanceById', 'getChildren'):
                raise
            return await self.raw(endpoint, payload, await self.auth(force=True))

    async def players(self, login):
        data = await self.call('getPlayersForCurrentAgent', {'start': 0, 'limit': 20,
            'filter': {'userName': {'action': '=', 'value': login, 'valueLabel': login}}})
        return data.get('records', []) if isinstance(data, dict) else []

    async def register(self, login, email, password):
        if not AGENT:
            raise IchancyError('ICHANCY_AGENT_ID غير مضبوط؛ مطلوب لإنشاء الحساب')
        return await self.call('registerPlayer', {'player': {'email': email, 'password': password,
                                                              'parentId': AGENT, 'login': login}})

    async def balance(self, pid):
        data = await self.call('getPlayerBalanceById', {'playerId': str(pid)})
        return next((x.get('balance') for x in data if isinstance(x, dict) and x.get('currencyCode') == 'NSP'), None) if isinstance(data, list) else None

    async def transfer(self, pid, amount, deposit, comment):
        from decimal import Decimal
        value = Decimal(str(amount))
        if not value.is_finite() or value <= 0:
            raise IchancyError('المبلغ غير صالح')
        data = {'amount': float(value if deposit else -value), 'comment': comment,
                'playerId': str(pid), 'currencyCode': 'NSP', 'currency': 'NSP', 'moneyStatus': 5}
        return await self.call('depositToPlayer' if deposit else 'withdrawFromPlayer', data)


client = Client()
