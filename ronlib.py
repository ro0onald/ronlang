"""RonLang standard library. No third-party dependencies."""
import html
import json
import math
import random
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from threading import RLock
from dataclasses import dataclass, field
from http import HTTPStatus
from urllib.parse import unquote
import re
from rondata import data_builtins
from ronfiles import FileResponse, download, static
from ronsecurity import Sessions, password_hash, password_verify, session_user, csrf, login, logout
import hmac
import logging
import mimetypes
import os
import time
from threading import BoundedSemaphore
from urllib.parse import quote


@dataclass
class Response:
    body: object
    status: int = 200
    headers: dict = field(default_factory=dict)

    def __post_init__(self):
        if type(self.status) is not int or self.status not in HTTPStatus._value2member_map_ or self.status < 200:
            raise ValueError('invalid response status')
        for name, value in self.headers.items():
            if not re.fullmatch(r'[A-Za-z0-9-]+', name) or '\r' in str(value) or '\n' in str(value):
                raise ValueError('invalid response header')
            if name.lower() in ('content-length', 'transfer-encoding', 'connection'):
                raise ValueError('reserved response header')


def element(tag, text):
    return f'<{tag}>{html.escape(str(text))}</{tag}>'


def page(title, content):
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(str(title))}</title>'
            '<style>body{font:18px system-ui;max-width:960px;margin:40px auto;'
            'padding:0 20px;background:#101827;color:#eef2ff}a{color:#8cdcff}'
            'button{padding:12px 20px;cursor:pointer}canvas{max-width:100%}</style>'
            f'<body>{content}</body></html>')


def button(label, endpoint, target):
    # Encode both HTML and JavaScript contexts; labels never become script.
    code = ('fetch(' + json.dumps(str(endpoint)) + ').then(r=>{if(!r.ok)throw Error(r.status);'
            'return r.json()}).then(v=>{document.getElementById('
            + json.dumps(str(target)) + ').textContent=JSON.stringify(v)})'
            '.catch(e=>alert(e.message))')
    return f'<button onclick="{html.escape(code, quote=True)}">{html.escape(str(label))}</button>'


def form(label, endpoint, fields, target):
    inputs = ''.join('<label>' + html.escape(str(name)) +
                     '<input required type="' + ('password' if str(name).lower() == 'password' else 'text') + '" name="' + html.escape(str(name), quote=True) + '"></label>'
                     for name in fields)
    code = ('event.preventDefault();(async()=>{const headers={"Content-Type":"application/json"};'
            'const guard=await fetch("/_ron/csrf");if(guard.ok){headers["X-CSRF-Token"]=(await guard.json()).csrf}'
            'const r=await fetch(' + json.dumps(str(endpoint)) +
            ',{method:"POST",headers,body:JSON.stringify(Object.fromEntries(new FormData(this)))});'
            'if(!r.ok)throw Error(await r.text());document.getElementById(' + json.dumps(str(target)) +
            ').textContent=JSON.stringify(await r.json())})().catch(e=>alert(e.message))')
    return ('<form onsubmit="' + html.escape(code, quote=True) + '">' + inputs +
            '<button type="submit">' + html.escape(str(label)) + '</button></form>')


def game(title, width, height, speed=240, color="#55ddff"):
    """A keyboard-controlled canvas scene that can be embedded in any page."""
    width, height, speed = int(width), int(height), float(speed)
    if not (64 <= width <= 4096 and 64 <= height <= 4096 and 0 < speed <= 10000):
        raise ValueError("invalid game dimensions or speed")
    config = json.dumps([width, height, speed, str(color)]).replace('<', '\\u003c')
    return element('h1', title) + f'''<p>Move: arrows or WASD. Collect the gold squares!</p>
<canvas width="{width}" height="{height}" tabindex="0" aria-label="Game"></canvas>
<script>(()=>{{
const [w,h,speed,color]={config};
const canvas=document.currentScript.previousElementSibling;
const ctx=canvas.getContext('2d'),keys=new Set();let x=10,y=10,score=0,last;
let goal={{x:Math.random()*(w-20),y:Math.random()*(h-20)}};
canvas.addEventListener('keydown',e=>{{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','w','a','s','d'].includes(e.key)){{keys.add(e.key);e.preventDefault()}}}});
canvas.addEventListener('keyup',e=>keys.delete(e.key));
canvas.addEventListener('blur',()=>keys.clear());canvas.focus();
function frame(t){{const dt=last===undefined?0:Math.min((t-last)/1000,.05);last=t;
x+=((keys.has('ArrowRight')||keys.has('d'))-(keys.has('ArrowLeft')||keys.has('a')))*speed*dt;
y+=((keys.has('ArrowDown')||keys.has('s'))-(keys.has('ArrowUp')||keys.has('w')))*speed*dt;
x=Math.max(0,Math.min(w-20,x));y=Math.max(0,Math.min(h-20,y));
if(x<goal.x+16&&x+20>goal.x&&y<goal.y+16&&y+20>goal.y){{score++;goal={{x:Math.random()*(w-20),y:Math.random()*(h-20)}}}}
ctx.fillStyle='#17253a';ctx.fillRect(0,0,w,h);ctx.fillStyle=color;ctx.fillRect(x,y,20,20);
ctx.fillStyle='gold';ctx.fillRect(goal.x,goal.y,16,16);ctx.fillStyle='white';ctx.font='18px system-ui';ctx.fillText('Score: '+score,10,25);requestAnimationFrame(frame)}}
requestAnimationFrame(frame);
}})();</script>'''


class LimitedServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        self.capacity = BoundedSemaphore(32)
        super().__init__(*args, **kwargs)

    def process_request(self, request, address):
        if not self.capacity.acquire(blocking=False):
            try:
                request.settimeout(1)
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n')
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.capacity.release()
            raise

    def process_request_thread(self, *args):
        try:
            super().process_request_thread(*args)
        finally:
            self.capacity.release()


class App:
    def __init__(self):
        self.routes, self.static_routes = {}, {}
        self.lock = RLock()
        self.sessions = None
        self.rate = {}

    def add(self, method, path, handler):
        if not isinstance(path, str) or not path.startswith('/') or '?' in path:
            raise ValueError('route path must start with / and have no query')
        names = re.findall(r'<([A-Za-z_]\w*)>', path)
        if len(set(names)) != len(names):
            raise ValueError('duplicate route parameter')
        self.routes[(method.upper(), path)] = handler

    def resolve(self, method, path):
        if (method, path) in self.routes:
            return self.routes[(method, path)], {}
        for (verb, route), handler in self.routes.items():
            names = re.findall(r'<([A-Za-z_]\w*)>', route)
            pattern = re.escape(route)
            for name in names:
                pattern = pattern.replace(re.escape('<' + name + '>'), '([^/]+)', 1)
            match = re.fullmatch(pattern, path)
            if verb == method and match:
                return handler, dict(zip(names, (unquote(value) for value in match.groups())))
        if method == 'GET':
            for prefix, root in self.static_routes.items():
                if path.startswith(prefix):
                    return FileResponse(root, unquote(path[len(prefix):])), {}
        return None, {}

    def server(self, port, host='127.0.0.1'):
        app = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(10)

            def log_message(self, format, *args):
                # Avoid logging query values, cookies or credentials.
                pass

            def log_request(self, code='-', size='-'):
                logging.getLogger('ronlang.http').info(json.dumps({'method': self.command, 'status': code}))

            def file(self, response):
                path = response.path()
                with path.open('rb') as stream:
                    self.send_response(200)
                    self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
                    self.send_header('Content-Length', str(os.fstat(stream.fileno()).st_size))
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    if response.attachment:
                        self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(path.name, safe=''))
                    self.end_headers()
                    if self.command != 'HEAD':
                        while chunk := stream.read(65536):
                            self.wfile.write(chunk)

            def dispatch(self):
                parts = urlsplit(self.path)
                method = 'GET' if self.command == 'HEAD' else self.command
                handler, params = app.resolve(method, parts.path)
                is_csrf = parts.path == '/_ron/csrf' and method == 'GET' and app.sessions is not None
                if handler is None and not is_csrf:
                    self.send_error(404)
                    return
                try:
                    if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) > 1:
                        self.send_error(400)
                        return
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 <= length <= 1048576:
                        self.send_error(413)
                        return
                    raw = self.rfile.read(length) if length else b''
                    if len(raw) != length:
                        self.send_error(400)
                        return
                    body = json.loads(raw) if raw else None
                    request = {'method': self.command, 'path': parts.path, 'params': params,
                               'query': parse_qs(parts.query), 'body': body, '_app': app,
                               'headers': {k.lower(): v for k, v in self.headers.items()}}
                    with app.lock:
                        now = time.monotonic()
                        app.rate = {key: value for key, value in app.rate.items() if now-value[0] < 60}
                        key = self.client_address[0]
                        started, count = app.rate.get(key, (now, 0))
                        app.rate[key] = (started, count+1)
                        if count >= 120 or len(app.rate) > 10000:
                            self.send_error(429)
                            return
                        if app.sessions is not None:
                            token, record = app.sessions.load(request['headers'].get('cookie', ''))
                            request['_session_token'], request['_session'] = token, record
                            if method not in ('GET', 'OPTIONS'):
                                supplied = request['headers'].get('x-csrf-token', '')
                                if not hmac.compare_digest(record['csrf'], supplied):
                                    self.send_error(403)
                                    return
                        result = {'csrf': csrf(request)} if is_csrf else handler(request) if callable(handler) else handler
                        result = result if isinstance(result, (Response, FileResponse)) else Response(result)
                        if isinstance(result, Response) and app.sessions is not None:
                            result = Response(result.body, result.status, dict(result.headers))
                            result.headers['Set-Cookie'] = app.sessions.cookie(request['_session_token'], request.get('_clear_session', False))
                            result.headers.setdefault('Cache-Control', 'no-store')
                    if isinstance(result, FileResponse):
                        self.file(result)
                        return
                    payload = result.body
                    if isinstance(payload, bytes):
                        content, mime = payload, 'application/octet-stream'
                    elif isinstance(payload, str):
                        content, mime = payload.encode('utf-8'), 'text/html; charset=utf-8'
                    else:
                        content, mime = json.dumps(payload, allow_nan=False).encode('utf-8'), 'application/json; charset=utf-8'
                    if result.status in (204, 304):
                        content = b''
                except FileNotFoundError:
                    self.send_error(404)
                    return
                except (ValueError, UnicodeError):
                    self.send_error(400)
                    return
                except Exception:
                    logging.getLogger('ronlang.http').exception('request failed')
                    self.send_error(500)
                    return
                self.send_response(result.status)
                if not any(key.lower() == 'content-type' for key in result.headers):
                    self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(content)))
                self.send_header('X-Content-Type-Options', 'nosniff')
                for name, value in result.headers.items():
                    self.send_header(name, str(value))
                self.end_headers()
                if self.command != 'HEAD':
                    self.wfile.write(content)

            do_GET = dispatch
            do_HEAD = dispatch
            do_POST = dispatch
            do_PUT = dispatch
            do_PATCH = dispatch
            do_DELETE = dispatch

        return LimitedServer((host, int(port)), Handler)


def serve(app, port=8000, host='127.0.0.1'):
    with app.server(port, host) as server:
        print(f'RonLang: http://{host}:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def write(path, value):
    Path(path).write_text(str(value), encoding='utf-8')


def put(collection, key, value):
    collection[key] = value
    return collection


def builtins():
    return {
        **data_builtins(),
        'text': str, 'number': float, 'integer': int, 'length': len,
        'range': range, 'abs': abs, 'round': round, 'min': min, 'max': max,
        'sqrt': math.sqrt, 'random': random.randint, 'ask': input,
        'append': lambda items, value: items.append(value), 'put': put,
        'read': lambda path: Path(path).read_text(encoding='utf-8'), 'write': write,
        'json': json.dumps, 'parse_json': json.loads,
        'app': App, 'serve': serve,
        'get': lambda app, path, handler: app.add('GET', path, handler),
        'post': lambda app, path, handler: app.add('POST', path, handler),
        'route': lambda app, method, path, handler: app.add(method.upper(), path, handler),
        'response': Response,
        'page': page, 'heading': lambda text: element('h1', text),
        'paragraph': lambda text: element('p', text),
        'output': lambda name: '<pre id="' + html.escape(str(name), quote=True) + '"></pre>',
        'button': button, 'game': game,
        'form': form,
        'download': download, 'descarga': download, 'static': static,
        'sessions': lambda app, secure=True, ttl=3600: setattr(app, 'sessions', Sessions(secure, ttl)),
        'password_hash': password_hash, 'password_verify': password_verify,
        'session_user': session_user, 'csrf': csrf, 'login': login, 'logout': logout,
        'link': lambda label, url: '<a href="' + safe_url(url) + '">' + html.escape(str(label)) + '</a>',
        'image': lambda url, alt='': '<img src="' + safe_url(url) + '" alt="' + html.escape(str(alt), quote=True) + '">',
        'stylesheet': lambda url: '<link rel="stylesheet" href="' + safe_url(url) + '">',
        'script': lambda url: '<script src="' + safe_url(url) + '" defer></script>',
        'navigation': lambda items: '<nav>' + ' '.join('<a href="' + safe_url(url) + '">' + html.escape(label) + '</a>' for label, url in items.items()) + '</nav>',
        'card': lambda title, content: '<section>' + element('h2', title) + str(content) + '</section>',
    }


def safe_url(url):
    url = str(url)
    if urlsplit(url).scheme.lower() not in ('', 'http', 'https'):
        raise ValueError('only relative or HTTP(S) URLs are allowed')
    if any(ord(char) < 32 for char in url) or '\\' in url:
        raise ValueError('invalid URL')
    return html.escape(url, quote=True)
