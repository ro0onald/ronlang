import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from ron import calculate, run_file, run_statements
from rondata import dot, fit_line, matrix_multiply, read_csv, write_csv, sql, valid, http_json
from ronlib import App, Response, builtins, form


class Language05Tests(unittest.TestCase):
    def test_spanish_and_english_aliases(self):
        variables = {}
        run_statements('''crear price es 20
let tax be 2
funcion sumar(a, b)
devolver a + b
fin
si verdadero y no falso
guardar result es sumar(price, tax)
sino
crear result es 0
fin
crear seen es []
para name en ["si", "crear", "y"]
append(seen, name)
fin'''.splitlines(), variables)
        self.assertEqual(variables['result'], 22)
        self.assertEqual(variables['seen'], ['si', 'crear', 'y'])
        self.assertEqual(calculate('"y no o"', {}), 'y no o')
        self.assertEqual(calculate('x + y', {'x': 2, 'y': 3}), 5)
        self.assertEqual(calculate('y', {'y': 3}), 3)

    def test_comparisons_short_circuit(self):
        self.assertTrue(calculate('1 < 2 <= 3', {}))
        self.assertFalse(calculate('3 < 2 < missing()', {}))
        self.assertTrue(calculate('2 in [1, 2]', {}))
        self.assertTrue(calculate('4 not in [1, 2]', {}))

    def test_loop_control(self):
        variables = {}
        run_statements('''crear count es 0
para n en range(8)
si n == 1
continuar
fin
si n == 4
romper
fin
repeat 3
make count = count + 1
break
end
fin
make i = 0
while true
make i = i + 1
when i < 2
continue
end
break
end'''.splitlines(), variables)
        self.assertEqual(variables['count'], 3)
        self.assertEqual(variables['i'], 2)
        for statement in ('break', 'continue', 'require false', 'exigir falso'):
            with self.subTest(statement=statement), self.assertRaises(ValueError):
                run_statements([statement], {})

    def test_function_cannot_break_caller_loop(self):
        with self.assertRaisesRegex(ValueError, 'outside a loop'):
            run_statements('func f()\nbreak\nend\nrepeat 2\nf()\nend'.splitlines(), {})

    def test_modules_relative_and_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'lib').mkdir()
            (root / 'lib' / 'constant.ron').write_text('make answer = 42')
            (root / 'lib' / 'helper.ron').write_text('use "constant.ron"\nfunc read_answer()\nreturn answer\nend')
            (root / 'main.ron').write_text('use "lib/helper.ron"\nshow read_answer()')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                run_file(root / 'main.ron')
            self.assertEqual(output.getvalue().strip(), '42')
            (root / 'cycle.ron').write_text('use "cycle.ron"')
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                run_file(root / 'cycle.ron')
            self.assertIn('circular module', output.getvalue())

    def test_cli_version_and_invalid_expression(self):
        result = subprocess.run([sys.executable, 'ron.py', '--version'], capture_output=True, text=True)
        from ron import __version__
        self.assertEqual(result.stdout.strip(), 'RonLang ' + __version__)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.ron'
            path.write_text('show (')
            result = subprocess.run([sys.executable, 'ron.py', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('Error in', result.stdout)
            self.assertNotIn('Traceback', result.stderr)


class Data05Tests(unittest.TestCase):
    def test_math_and_learning(self):
        library = builtins()
        self.assertEqual(dot([1, 2], [3, 4]), 11)
        self.assertEqual(matrix_multiply([[1, 2]], [[3], [4]]), [[11]])
        model = fit_line([1, 2, 3], [3, 5, 7])
        self.assertAlmostEqual(library['predict'](model, 10), 21)
        self.assertEqual(library['mean']([2, 4, 6]), 4)
        self.assertEqual(library['median']([2, 6, 4]), 4)
        for function, args in [(dot, ([1], [1, 2])), (fit_line, ([1, 1], [2, 3])),
                               (matrix_multiply, ([[1, 2]], [[1, 2]])),
                               (matrix_multiply, ([[1], [1, 2]], [[1]]))]:
            with self.subTest(function=function.__name__), self.assertRaises(ValueError):
                function(*args)

    def test_csv_sql_and_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            rows = [{'name': 'Ron, "hola"', 'value': 'é'}]
            write_csv(path / 'data.csv', rows)
            self.assertEqual(read_csv(path / 'data.csv'), rows)
            db = str(path / 'test.sqlite3')
            sql(db, 'CREATE TABLE names (name TEXT)')
            value = "x'); DROP TABLE names; --"
            sql(db, 'INSERT INTO names VALUES (?)', [value])
            self.assertEqual(sql(db, 'SELECT name FROM names'), [{'name': value}])
            with self.assertRaises(ValueError):
                sql(db, 'SELECT missing FROM names')

    def test_schema_and_functional_data(self):
        self.assertTrue(valid({'age': 42}, {'age': 'integer'}))
        self.assertFalse(valid({'age': True}, {'age': 'integer'}))
        self.assertFalse(valid({}, {'name': 'text'}))
        self.assertFalse(valid(None, {'name': 'text'}))
        variables = {}
        run_statements('func square(x)\nreturn x*x\nend\nmake results = map(square, [2,3])'.splitlines(), variables)
        self.assertEqual(variables['results'], [4, 9])


class Service05Tests(unittest.TestCase):
    def test_response_validation(self):
        for status in (99, 999, 200.0):
            with self.assertRaises(ValueError):
                Response({}, status)
        for headers in ({'X-Test': 'bad\r\nInjected: yes'}, {'Content-Length': '1'}, {'bad name': 'value'}):
            with self.assertRaises(ValueError):
                Response({}, headers=headers)
        self.assertIn('&lt;', form('<label>', '/api', ['name'], 'result'))

    def test_startup_crud_and_client(self):
        with tempfile.TemporaryDirectory() as directory:
            functions = builtins()
            apps = []
            functions['serve'] = lambda *args: apps.append(args[0])
            with patch.dict(os.environ, {'RON_DATABASE': str(Path(directory) / 'app.sqlite3')}):
                run_statements(Path('examples/startup.ron').read_text(encoding='utf-8').splitlines(), {}, functions)
            app = apps[0]
            with app.server(0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f'http://127.0.0.1:{server.server_port}'
                try:
                    self.assertEqual(http_json(base + '/health')['version'], '0.5.0')
                    request = Request(base + '/api/tasks', data=json.dumps({'title': 'Hola'}).encode(), method='POST')
                    with urlopen(request) as result:
                        self.assertEqual(result.status, 201)
                    self.assertEqual(http_json(base + '/api/tasks'), [{'id': 1, 'title': 'Hola'}])
                    with urlopen(Request(base + '/api/tasks/1', method='DELETE')) as result:
                        self.assertEqual(json.load(result), {'deleted': 1})
                    self.assertEqual(http_json(base + '/api/tasks'), [])
                    for request, status in [(Request(base+'/api/tasks', data=b'{}'), 400),
                                            (Request(base+'/api/tasks/1', method='DELETE'), 404)]:
                        with self.assertRaises(HTTPError) as error:
                            urlopen(request)
                        self.assertEqual(error.exception.code, status)
                        error.exception.close()
                finally:
                    server.shutdown()
                    thread.join(timeout=3)

    def test_routing_and_headers(self):
        app = App()
        app.add('GET', '/users/<name>', lambda request: Response(request['params'], 200, {'X-Test': 'yes'}))
        app.add('GET', '/users/me', 'literal')
        self.assertEqual(app.resolve('GET', '/users/me'), ('literal', {}))
        self.assertEqual(app.resolve('GET', '/users/Ron%20Lang')[1], {'name': 'Ron Lang'})
        self.assertEqual(app.resolve('POST', '/users/me'), (None, {}))

    def test_http_headers_and_body_limit(self):
        app = App()
        app.add('GET', '/custom', Response({'ok': True}, 202, {'X-Service': 'ron'}))
        app.add('GET', '/empty', Response(None, 204))
        app.add('POST', '/body', lambda request: request['body'])
        with app.server(0) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(base + '/custom') as response:
                    self.assertEqual(response.status, 202)
                    self.assertEqual(response.headers['X-Service'], 'ron')
                    self.assertEqual(json.load(response), {'ok': True})
                with urlopen(base + '/empty') as response:
                    self.assertEqual(response.status, 204)
                    self.assertEqual(response.read(), b'')
                request = Request(base + '/body', data=b'', headers={'Content-Length': '1048577'})
                with self.assertRaises(HTTPError) as error:
                    urlopen(request)
                self.assertEqual(error.exception.code, 413)
                error.exception.close()
            finally:
                server.shutdown()
                thread.join(timeout=3)
