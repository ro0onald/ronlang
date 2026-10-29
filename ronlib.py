"""RonLang standard library. No third-party dependencies."""
import html
import json
import math
import random
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from threading import RLock


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


class App:
    def __init__(self):
        self.routes = {}
        self.lock = RLock()

    def add(self, method, path, handler):
        if not isinstance(path, str) or not path.startswith('/') or '?' in path:
            raise ValueError("route path must start with / and have no query")
        self.routes[(method, path)] = handler

    def server(self, port, host='127.0.0.1'):
        app = self

        class Handler(BaseHTTPRequestHandler):
            def dispatch(self):
                parts = urlsplit(self.path)
                handler = app.routes.get((self.command, parts.path))
                if handler is None:
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if length < 0 or length > 1048576:
                        self.send_error(413)
                        return
                    body = json.loads(self.rfile.read(length)) if length else None
                    request = {'method': self.command, 'path': parts.path,
                               'query': parse_qs(parts.query), 'body': body}
                    with app.lock:
                        response = handler(request) if callable(handler) else handler
                    if isinstance(response, str):
                        content, mime = response.encode('utf-8'), 'text/html; charset=utf-8'
                    else:
                        content, mime = json.dumps(response).encode('utf-8'), 'application/json; charset=utf-8'
                except (ValueError, UnicodeError):
                    self.send_error(400)
                    return
                except Exception:
                    self.send_error(500)
                    return
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(content)))
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                self.wfile.write(content)

            do_GET = dispatch
            do_POST = dispatch

        return ThreadingHTTPServer((host, int(port)), Handler)


def serve(app, port=8000):
    with app.server(port) as server:
        print(f'RonLang: http://127.0.0.1:{server.server_port}', flush=True)
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
        'text': str, 'number': float, 'integer': int, 'length': len,
        'range': range, 'abs': abs, 'round': round, 'min': min, 'max': max,
        'sqrt': math.sqrt, 'random': random.randint, 'ask': input,
        'append': lambda items, value: items.append(value), 'put': put,
        'read': lambda path: Path(path).read_text(encoding='utf-8'), 'write': write,
        'json': json.dumps, 'parse_json': json.loads,
        'app': App, 'serve': serve,
        'get': lambda app, path, handler: app.add('GET', path, handler),
        'post': lambda app, path, handler: app.add('POST', path, handler),
        'page': page, 'heading': lambda text: element('h1', text),
        'paragraph': lambda text: element('p', text),
        'output': lambda name: '<pre id="' + html.escape(str(name), quote=True) + '"></pre>',
        'button': button, 'game': game,
    }
