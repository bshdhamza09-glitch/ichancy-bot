"""Offline API client contract tests. No real Ichancy requests or credentials."""
import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import ichancy_api as api


class ClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = patch.object(api, 'TOKEN_FILE', Path(self.tmp.name)/'tokens.json')
        patcher.start(); self.addCleanup(patcher.stop)

    async def test_refresh_rotates_and_persists_pair(self):
        client = api.Client()
        client.refresh = 'old_refresh'
        client.refresh_expires = time.time() + 3600
        client.raw = AsyncMock(return_value={'accessToken':'new_access', 'refreshToken':'new_refresh'})
        result = await client.auth()
        self.assertEqual(result, 'new_access')
        client.raw.assert_awaited_once_with('refreshToken', {'refreshToken':'old_refresh'})
        self.assertEqual(json.loads(api.TOKEN_FILE.read_text())['refresh'], 'new_refresh')
        restored = api.Client()
        self.assertEqual(restored.access, 'new_access')
        self.assertEqual(restored.refresh, 'new_refresh')

    async def test_403_refresh_does_not_trigger_signin(self):
        client = api.Client()
        client.refresh = 'old_refresh'
        client.refresh_expires = time.time() + 3600
        client.raw = AsyncMock(side_effect=api.IchancyForbidden('Cloudflare 403'))
        with self.assertRaises(api.IchancyForbidden):
            await client.auth()
        self.assertEqual(client.raw.await_count, 1)
        self.assertEqual(client.raw.await_args.args[0], 'refreshToken')

    async def test_invalid_refresh_allows_signin(self):
        client = api.Client()
        client.refresh = 'old_refresh'
        client.refresh_expires = time.time() + 3600
        async def call(endpoint, payload, token=None):
            if endpoint=='refreshToken':raise api.IchancyAuthExpired('expired')
            self.assertEqual(endpoint, 'signin')
            return {'accessToken':'valid_access','refreshToken':'valid_refresh'}
        client.raw = AsyncMock(side_effect=call)
        with patch.object(api, 'USER', 'test_agent'), patch.object(api, 'PASSWORD', 'test_password'):
            result = await client.auth()
        self.assertEqual(result,'valid_access')
        self.assertEqual(client.raw.await_count,2)

    async def test_mutations_are_not_retried_after_ambiguous_auth(self):
        client=api.Client()
        client.auth=AsyncMock(return_value='token')
        client.raw=AsyncMock(side_effect=api.IchancyAuthExpired('expired'))
        with self.assertRaises(api.IchancyAuthExpired):
            await client.call('registerPlayer', {'player': {}})
        self.assertEqual(client.raw.await_count,1)

    async def test_reads_only_retry_after_definite_expired_token(self):
        client=api.Client()
        client.auth=AsyncMock(side_effect=['old','new'])
        client.raw=AsyncMock(side_effect=[api.IchancyAuthExpired('expired'), [{'currencyCode':'NSP'}]])
        result=await client.call('getAgentAllWallets', {})
        self.assertEqual(result,[{'currencyCode':'NSP'}])
        self.assertEqual(client.raw.await_count,2)
        self.assertEqual(client.auth.await_count,2)

    async def test_forbidden_html_is_identified_without_cookies(self):
        class FakeResponse:
            status=403
            headers={'Content-Type':'text/html; charset=UTF-8','CF-Ray':'abc123-IAD'}
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            content=None
            async def json(self,*a,**kw):raise AssertionError('should not parse HTML')
        FakeResponse.content=type('FakeBody', (), {'read': AsyncMock(return_value=b'<html><title>Just a moment</title></html>')})()
        class FakeSession:
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            def post(self,*a,**kw):return FakeResponse()
        with patch.object(api.aiohttp,'ClientSession',return_value=FakeSession()):
            with self.assertRaises(api.IchancyForbidden) as caught:
                await api.Client().raw('signin', {'username':'x','password':'y'})
        self.assertIn('abc123-IAD',str(caught.exception))
        self.assertNotIn('password',str(caught.exception))


    async def test_documented_201_ex_is_expired_access_not_success(self):
        class FakeResponse:
            status=201
            headers={'Content-Type':'application/json'}
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            async def json(self,**kwargs): return {'status':True,'result':'ex','notification':[]}
        class FakeSession:
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            def post(self,*args,**kwargs):return FakeResponse()
        with patch.object(api.aiohttp,'ClientSession',return_value=FakeSession()):
            with self.assertRaises(api.IchancyAuthExpired):
                await api.Client().raw('getAgentAllWallets', {}, token='fake')

    async def test_201_ex_refreshes_read_only_request(self):
        client=api.Client()
        client.auth=AsyncMock(side_effect=['old','new'])
        client.raw=AsyncMock(side_effect=[api.IchancyAuthExpired('201 ex'), [{'currencyCode':'NSP'}]])
        self.assertEqual(await client.call('getAgentAllWallets',{}),[{'currencyCode':'NSP'}])
        self.assertEqual(client.raw.await_count,2)

    async def test_201_ex_does_not_replay_mutation(self):
        client=api.Client()
        client.auth=AsyncMock(return_value='old')
        client.raw=AsyncMock(side_effect=api.IchancyAuthExpired('201 ex'))
        with self.assertRaises(api.IchancyAuthExpired):
            await client.call('registerPlayer', {'player': {}})
        self.assertEqual(client.raw.await_count,1)

    async def test_201_signin_rejection_is_not_expired_access(self):
        class FakeResponse:
            status=201
            headers={'Content-Type':'application/json'}
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def json(self,**kwargs):return {'status':True,'result':False,'notification':[{'content':'Invalid username or password.'}]}
        class FakeSession:
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            def post(self,*args,**kwargs):return FakeResponse()
        with patch.object(api.aiohttp,'ClientSession',return_value=FakeSession()):
            with self.assertRaises(api.IchancyError) as cm:
                await api.Client().raw('signin', {'username':'bad','password':'bad'})
        self.assertNotIsInstance(cm.exception,api.IchancyAuthExpired)
        self.assertIn('Invalid username',str(cm.exception))


if __name__=='__main__':unittest.main()
