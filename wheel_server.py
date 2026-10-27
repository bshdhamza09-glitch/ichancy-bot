"""Telegram authenticated wheel mini app. Shares SQLite with the bot."""
import os, json, hmac, hashlib, time, sqlite3, asyncio
from pathlib import Path
from urllib.parse import parse_qsl
from aiohttp import web

DB=Path(os.getenv('DATABASE_PATH',str(Path(__file__).with_name('sheikh.db'))))
TOKEN=os.getenv('BOT_TOKEN','')
BASE=Path(__file__).with_name('miniapp')

def connect():
    c=sqlite3.connect(DB,timeout=15,isolation_level=None)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA busy_timeout=15000')
    return c

def setup():
    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS wheel_spins (deposit_id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,awarded_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS wheel_plays (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,outcome TEXT NOT NULL,played_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS wheel_bonuses (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,percent INTEGER NOT NULL DEFAULT 5,expires_at INTEGER NOT NULL,used_deposit_id INTEGER UNIQUE)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_wheel_spins_user ON wheel_spins(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_wheel_plays_user ON wheel_plays(user_id)')

def identity(request):
    try:
        data=json.loads(request.get('body','{}')); raw=data['initData']; params=dict(parse_qsl(raw,keep_blank_values=True)); received=params.pop('hash')
        check='\n'.join(f'{k}={v}' for k,v in sorted(params.items()))
        secret=hmac.new(b'WebAppData',TOKEN.encode(),hashlib.sha256).digest()
        expected=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,received) or abs(time.time()-int(params['auth_date']))>86400:raise ValueError()
        return int(json.loads(params['user'])['id'])
    except Exception:raise web.HTTPUnauthorized(text=json.dumps({'error':'تعذر التحقق من حساب تلغرام'}),content_type='application/json')

async def parse(request):
    request['body']=await request.text()
    return identity(request)

def stats(c,uid):
    earned=c.execute('SELECT COUNT(*) FROM wheel_spins WHERE user_id=?',(uid,)).fetchone()[0]
    spent=c.execute('SELECT COUNT(*) FROM wheel_plays WHERE user_id=?',(uid,)).fetchone()[0]
    return {'spins':max(0,earned-spent),'progress':spent%11}

async def status(request):
    uid=await parse(request)
    with connect() as c:return web.json_response(stats(c,uid))

async def spin(request):
    uid=await parse(request)
    with connect() as c:
        try:
            c.execute('BEGIN IMMEDIATE')
            s=stats(c,uid)
            if s['spins']<1:
                c.rollback();return web.json_response({'error':'ما عندك لفات متاحة'},status=400)
            outcome='bonus' if s['progress']==10 else 'hardluck'
            c.execute('INSERT INTO wheel_plays(user_id,outcome) VALUES(?,?)',(uid,outcome))
            if outcome=='bonus':c.execute('INSERT INTO wheel_bonuses(user_id,percent,expires_at) VALUES(?,5,?)',(uid,int(time.time())+86400))
            c.commit()
            return web.json_response({'outcome':outcome})
        except Exception:
            c.rollback();raise

async def page(request):
    return web.Response(body=(BASE/'index.html').read_bytes(),content_type='text/html',charset='utf-8',headers={'Cache-Control':'no-store'})
async def video(request):
    return web.Response(body=(BASE/'hardluck.mp4').read_bytes(),content_type='video/mp4')
async def health(request):return web.json_response({'ok': True, 'service': 'sheikh-wheel', 'version': 'V31'})

def create_app():
    setup(); app=web.Application(client_max_size=8192)
    app.router.add_get('/',page);app.router.add_get('/wheel',page);app.router.add_get('/wheel/',page);app.router.add_get('/health',health);app.router.add_get('/miniapp/hardluck.mp4',video)
    app.router.add_post('/api/status',status);app.router.add_post('/api/spin',spin)
    return app

async def serve():
    runner=web.AppRunner(create_app());await runner.setup()
    site=web.TCPSite(runner,'0.0.0.0',int(os.getenv('PORT','8080')));await site.start()
    return runner
