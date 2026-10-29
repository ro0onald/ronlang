import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPCookieProcessor, urlopen
from unittest.mock import patch

from ron import RonError, SourceLines, run_statements
from roncli import diagnostics, format_source, main
from rondata import migrate, sql, postgres
from ronfiles import download, static
from ronlib import App, Response, builtins
from ronsecurity import Sessions, password_hash, password_verify, login, logout, session_user
from ronstarter import create_project


@contextlib.contextmanager
def running(app):
    with app.server(0) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}'
        finally:
            server.shutdown()
            thread.join(timeout=3)


class RuntimeTests(unittest.TestCase):
    def test_error_locations_and_catch(self):
        source = SourceLines('func fail()\nwhen true\nshow unknown\nend\nend\nfail()'.splitlines(), 'sample.ron')
        with self.assertRaises(RonError) as caught:
            run_statements(source, {})
        self.assertEqual(caught.exception.line, 3)
        self.assertEqual(caught.exception.source, 'sample.ron')
        variables = {}
        run_statements('try\nshow 1 / 0\ncatch problem\nmake message = problem["message"]\nend'.splitlines(), variables)
        self.assertIn('division by zero', variables['message'])

    def test_control_signals_are_not_caught(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run_statements('func f()\ntry\nreturn 42\ncatch error\nreturn 0\nend\nend\nshow f()'.splitlines(), {})
        self.assertEqual(output.getvalue(), '42\n')

    def test_checker_no_side_effects_and_formatter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'check.ron'
            path.write_text('when true\nshow 1\nend\n')
            self.assertEqual(diagnostics(path), [])
            self.assertEqual(format_source(path.read_text()), 'when true\n    show 1\nend\n')
            path.write_text('return 2\nend\nshow (\n')
            self.assertEqual([item['line'] for item in diagnostics(path)], [1, 2, 3])

    def test_new_starter_and_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'website'
            create_project(root)
            self.assertEqual(diagnostics(root / 'main.ron'), [])
            functions, apps = builtins(), []
            functions['serve'] = lambda *args: apps.append(args[0])
            run_statements((root / 'main.ron').read_text().splitlines(), {}, functions)
            with running(apps[0]) as base:
                with urlopen(base + '/download') as response:
                    self.assertEqual(response.read(), (root / 'files/welcome.txt').read_bytes())
                with urlopen(base + '/assets/style.css') as response:
                    self.assertIn(b'color', response.read())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['test', str(root)]), 0)

    def test_migration_atomicity_and_immutability(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = str(root / 'app.sqlite3')
            migrations = root / 'migrations'
            migrations.mkdir()
            first = migrations / '001.sql'
            first.write_text('CREATE TABLE users (id INTEGER); INSERT INTO users VALUES (1);')
            self.assertEqual(migrate(db, migrations), 1)
            self.assertEqual(migrate(db, migrations), 0)
            bad = migrations / '002.sql'
            bad.write_text('INSERT INTO users VALUES (2); INSERT INTO missing VALUES (3);')
            with self.assertRaises(ValueError):
                migrate(db, migrations)
            self.assertEqual(sql(db, 'SELECT * FROM users'), [{'id': 1}])
            bad.write_text('-- bypass attempt\nCOMMIT;')
            with self.assertRaises(ValueError):
                migrate(db, migrations)
            first.write_text('CREATE TABLE changed (id INTEGER);')
            with self.assertRaisesRegex(ValueError, 'changed'):
                migrate(db, migrations)


class FilesTests(unittest.TestCase):
    def test_download_head_and_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / 'public'
            public.mkdir()
            data = bytes(range(256)) * 1024
            (public / 'file.zip').write_bytes(data)
            (root / 'secret.txt').write_text('SECRET')
            app = App()
            static(app, '/assets/', public)
            download(app, '/download', public / 'file.zip')
            with running(app) as base:
                with urlopen(base + '/download') as response:
                    self.assertEqual(response.read(), data)
                    self.assertIn('attachment', response.headers['Content-Disposition'])
                with urlopen(Request(base + '/download', method='HEAD')) as response:
                    self.assertEqual(int(response.headers['Content-Length']), len(data))
                    self.assertEqual(response.read(), b'')
                for suffix in ('../secret.txt', '%2e%2e/secret.txt', '%2fsecret.txt', 'missing'):
                    with self.subTest(suffix=suffix), self.assertRaises(HTTPError) as caught:
                        urlopen(base + '/assets/' + suffix)
                    self.assertEqual(caught.exception.code, 404)
                    caught.exception.close()

    def test_symlink_escape_when_available(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / 'public'
            public.mkdir()
            (root / 'secret').write_text('secret')
            try:
                (public / 'link').symlink_to(root / 'secret')
            except OSError:
                self.skipTest('symlink creation requires Windows developer mode or privilege')
            app = App()
            static(app, '/assets/', public)
            response, _ = app.resolve('GET', '/assets/link')
            with self.assertRaises(FileNotFoundError):
                response.path()


class SecurityTests(unittest.TestCase):
    def test_authenticated_example(self):
        functions, apps = builtins(), []
        functions['serve'] = lambda *args: apps.append(args[0])
        with patch.dict(os.environ, {'DEMO_PASSWORD': 'test-only-password', 'COOKIE_SECURE': 'false'}):
            run_statements(SourceLines(Path('examples/site/main.ron').read_text().splitlines(), 'examples/site/main.ron'), {}, functions)
        browser = build_opener(HTTPCookieProcessor(CookieJar()))
        with running(apps[0]) as base:
            with browser.open(base) as response:
                page = response.read().decode()
                self.assertIn('type="password"', page)
                self.assertNotIn('test-only-password', page)
            with browser.open(base + '/_ron/csrf') as response:
                token = json.load(response)['csrf']
            request = Request(base + '/api/login', data=b'{"password":"test-only-password"}', headers={'X-CSRF-Token': token})
            with browser.open(request) as response:
                self.assertEqual(json.load(response)['user'], 'demo')
            with browser.open(base + '/api/profile') as response:
                self.assertEqual(json.load(response), {'user': 'demo'})

    def test_passwords(self):
        encoded = password_hash('correct-horse-battery')
        self.assertTrue(password_verify('correct-horse-battery', encoded))
        self.assertFalse(password_verify('wrong', encoded))
        self.assertFalse(password_verify('password', 'malformed'))
        self.assertNotEqual(encoded, password_hash('correct-horse-battery'))

    def test_login_rotation_csrf_logout_and_expiry(self):
        app = App()
        app.sessions = Sessions(secure=False)
        app.add('POST', '/login', lambda request: login(request, 'alice'))
        app.add('POST', '/logout', logout)
        app.add('GET', '/me', lambda request: {'user': session_user(request)})
        jar = CookieJar()
        browser = build_opener(HTTPCookieProcessor(jar))
        with running(app) as base:
            def read(path):
                with browser.open(base + path) as response:
                    return json.load(response)
            csrf = read('/_ron/csrf')['csrf']
            old_cookie = list(jar)[0].value
            with self.assertRaises(HTTPError) as caught:
                browser.open(Request(base + '/login', data=b'{}'))
            self.assertEqual(caught.exception.code, 403)
            caught.exception.close()
            request = Request(base + '/login', data=b'{}', headers={'X-CSRF-Token': csrf})
            with browser.open(request) as response:
                self.assertIn('HttpOnly', response.headers['Set-Cookie'])
                self.assertEqual(json.load(response)['user'], 'alice')
            self.assertNotEqual(old_cookie, list(jar)[0].value)
            self.assertNotIn(old_cookie, app.sessions.records)
            self.assertEqual(read('/me'), {'user': 'alice'})
            csrf = read('/_ron/csrf')['csrf']
            with browser.open(Request(base+'/logout', data=b'{}', headers={'X-CSRF-Token': csrf})) as response:
                self.assertTrue(json.load(response)['logged_out'])
            self.assertEqual(read('/me'), {'user': None})
            for record in app.sessions.records.values():
                record['expires'] = 0
            self.assertEqual(read('/me'), {'user': None})

    def test_safe_links(self):
        library = builtins()
        with self.assertRaises(ValueError):
            library['link']('bad', 'javascript:alert(1)')
        self.assertIn('&lt;', library['link']('<name>', '/path'))
