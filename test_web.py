import contextlib
import io
import json
from pathlib import Path
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from ron import run_statements, calculate
from ronlib import App, page, element, game


class PlatformTests(unittest.TestCase):
    def test_collections_loops_logic(self):
        env = {}
        run_statements('''make items = []
for n in range(4)
append(items, n * n)
end
make i = 0
while i < 3
make i = i + 1
end
make data = {"items": items, "ok": true}
put(data, "count", i)
'''.splitlines(), env)
        self.assertEqual(env['data'], {'items': [0, 1, 4, 9], 'ok': True, 'count': 3})
        self.assertEqual(calculate('-2 ** 2 + 9 // 2', {}), 0)
        self.assertTrue(calculate('not false and true', {}))
        self.assertFalse(calculate('false and missing()', {}))
        self.assertTrue(calculate('true or missing()', {}))

    def test_html_escaping_and_game(self):
        self.assertIn('&lt;script&gt;', element('h1', '<script>'))
        document = page('<unsafe>', game('Demo', 800, 450))
        self.assertIn('<canvas', document)
        self.assertIn('requestAnimationFrame', document)
        self.assertIn('&lt;unsafe&gt;', document)
        with self.assertRaises(ValueError):
            game('bad', 0, 450)

    def test_example_http(self):
        # Execute the actual web example, replacing only its blocking serve call.
        from ronlib import builtins
        functions = builtins()
        apps = []
        functions['serve'] = lambda app, port: apps.append(app)
        run_statements(Path('examples/web.ron').read_text().splitlines(), {}, functions)
        with apps[0].server(0) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(base) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn('Call API', response.read().decode())
                with urlopen(base + '/api/hello') as response:
                    self.assertEqual(json.load(response)['message'], 'Hello from RonLang')
                    self.assertIn('application/json', response.headers['Content-Type'])
                request = Request(base + '/api/echo', data=b'{"score":42}', method='POST')
                with urlopen(request) as response:
                    self.assertEqual(json.load(response), {'score': 42})
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + '/missing')
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base + '/api/echo', data=b'not-json', method='POST'))
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
            finally:
                server.shutdown()
                thread.join(timeout=3)

    def test_game_example(self):
        from ronlib import builtins
        functions = builtins()
        apps = []
        functions['serve'] = lambda app, port: apps.append(app)
        run_statements(Path('examples/game.ron').read_text().splitlines(), {}, functions)
        self.assertIn('<canvas', apps[0].routes[('GET', '/')])

    def test_basics_example(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run_statements(Path('examples/basics.ron').read_text().splitlines(), {})
        self.assertIn('Hello, Mia', output.getvalue())
        self.assertIn('True', output.getvalue())
