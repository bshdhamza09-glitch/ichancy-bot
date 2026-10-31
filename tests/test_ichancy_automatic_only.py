"""Offline regression tests: Ichancy must never queue requests to admins."""
import importlib
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from test_ichancy_api import api

class Field:
    def __getattr__(self, _): return self
    def __eq__(self, other): return self
    def startswith(self,*args): return self
    def in_(self,*args): return self
class Handler:
    def __call__(self,*args,**kwargs):
        def decorate(fn): return fn
        return decorate
class Router:
    def __init__(self): self.message=Handler(); self.callback_query=Handler()
class Keyboard:
    def __init__(self,**kwargs): self.__dict__.update(kwargs)
class Base: pass

def stubs():
    a=types.ModuleType('aiogram'); a.Router=Router; a.F=Field(); sys.modules['aiogram']=a
    x=types.ModuleType('aiogram.filters'); x.Command=lambda *args:None; sys.modules[x.__name__]=x
    x=types.ModuleType('aiogram.types')
    for n in ('Message','CallbackQuery'):setattr(x,n,Base)
    for n in ('ReplyKeyboardMarkup','KeyboardButton','ReplyKeyboardRemove','InlineKeyboardMarkup','InlineKeyboardButton'):setattr(x,n,Keyboard)
    sys.modules[x.__name__]=x
    for n in ('aiogram.fsm','aiogram.fsm.context','aiogram.fsm.state'):
        sys.modules[n]=types.ModuleType(n)
    sys.modules['aiogram.fsm.context'].FSMContext=Base
    sys.modules['aiogram.fsm.state'].StatesGroup=Base
    sys.modules['aiogram.fsm.state'].State=lambda:object()
class State:
    def __init__(self): self.value=None
    async def clear(self): self.value=None
    async def set_state(self,value): self.value=value
class Bot:
    def __init__(self): self.sent=[]
    async def send_message(self,*args,**kwargs): self.sent.append((args,kwargs))
class Message:
    def __init__(self,bot,text=''):
        self.text=text; self.bot=bot; self.from_user=types.SimpleNamespace(id=12); self.answers=[]
    async def answer(self,text,**kwargs):self.answers.append((text,kwargs));return self
class Query:
    def __init__(self,bot):
        self.message=Message(bot); self.data='ichmanual:begin'; self.answered=[]
    async def answer(self,*args,**kwargs):self.answered.append((args,kwargs))

class AutomaticOnlyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        stubs();self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.database=Path(self.temp.name)/'bot.db'
        b=types.ModuleType('bot');b.DB=self.database;b.ADMIN_IDS={100};sys.modules['bot']=b
        sys.modules.pop('ichancy_handlers',None)
        self.module=importlib.import_module('ichancy_handlers')
        self.bot=Bot()

    async def test_no_manual_option_if_preflight_blocked(self):
        msg=Message(self.bot)
        with patch.object(self.module.client,'call',new=AsyncMock(side_effect=api.IchancyForbidden('403'))):
            await self.module.begin(msg,State())
        self.assertTrue(any('آلي فقط' in t for t,_ in msg.answers))
        self.assertFalse(any('طلب إنشاء يدوي' in repr(kw) for _,kw in msg.answers))
        self.assertEqual(self.bot.sent,[])
        with self.module.db() as con:
            table=con.execute("SELECT name FROM sqlite_master WHERE name='ichancy_manual_requests'").fetchone()
            self.assertIsNone(table)

    async def test_stale_manual_callback_is_disabled(self):
        q=Query(self.bot)
        await self.module.reject_legacy_manual_callback(q,State())
        self.assertEqual(self.bot.sent,[])
        self.assertTrue(q.answered)

if __name__=='__main__':unittest.main()
