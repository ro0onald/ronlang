import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ron import calculate, run_statements


class RonTests(unittest.TestCase):
    def execute(self, source):
        output = io.StringIO()
        variables = {}
        with contextlib.redirect_stdout(output):
            run_statements(source.splitlines(), variables)
        return output.getvalue(), variables

    def test_original_example(self):
        source = Path(__file__).with_name('hola.ron').read_text()
        self.assertEqual(self.execute(source)[0], '1\n2\n3\n4\n5\nLoop finished!\n')

    def test_arithmetic_and_comparisons(self):
        for expression, value in [('2 + 3 * 4', 14), ('8 / 2 - 1', 3), ('8 % 3', 2),
                                  ('1 == 1', True), ('1 != 2', True), ('1 < 2', True),
                                  ('2 <= 2', True), ('3 > 2', True), ('3 >= 3', True)]:
            with self.subTest(expression=expression):
                self.assertEqual(calculate(expression, {}), value)

    def test_functions_and_concatenation(self):
        output, variables = self.execute('''func greet(name)
show "Hello, " + name
end
func add(a, b)
return a + b
end
greet("Ronald")
make result = add(add(1, 2), 3) * 2
show result
show "a" + "b"
make text = "c" + "d"
show text''')
        self.assertEqual(output, 'Hello, Ronald\n12\nab\ncd\n')
        self.assertEqual(variables['result'], 12)

    def test_return_unwinds_nested_blocks(self):
        self.assertEqual(self.execute('''func choose(n)
repeat 3
when n > 0
return "yes"
otherwise
return "no"
end
end
show "unreachable"
end
show choose(2)
show choose(0)''')[0], 'yes\nno\n')

    def test_recursion_and_scope(self):
        output, variables = self.execute('''make n = 10
func factorial(n)
when n <= 1
return 1
end
return n * factorial(n - 1)
end
show factorial(5)
show n''')
        self.assertEqual(output, '120\n10\n')
        self.assertEqual(variables, {'n': 10})

    def test_globals_and_local_assignment(self):
        self.assertEqual(self.execute('''make x = 2
func read()
make x = x + 1
return x
end
make x = 5
show read()
show x''')[0], '6\n5\n')

    def test_nested_otherwise(self):
        self.assertEqual(self.execute('''when 1 == 1
when 1 == 2
show "bad"
otherwise
show "inner"
end
otherwise
show "bad"
end''')[0], 'inner\n')

    def test_function_blocks_and_no_return(self):
        self.assertEqual(self.execute('''when 1 == 1
func empty()
end
end
show empty()''')[0], 'None\n')

    def test_invalid_programs(self):
        programs = ['return 2', 'func bad(a, a)\nend', 'func bad(a,)\nend',
                    'func bad\nend', 'func bad()\nshow 1',
                    'func f(a)\nreturn a\nend\nf()',
                    'func f()\nend\nf(1)', 'missing()', 'show unknown',
                    'show "a" + 1', 'show 1 / 0', 'repeat 10001\nend',
                    'repeat 1.5\nend', 'end', 'otherwise', 'nonsense',
                    'show __import__("os")', 'show (1).__class__',
                    'func f(a)\nend\nf(a=1)']
        for source in programs:
            with self.subTest(source=source), self.assertRaises((ValueError, TypeError)):
                self.execute(source)

    def test_cli(self):
        interpreter = str(Path(__file__).with_name('ron.py'))
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory) / 'test.ron'
            program.write_text('func sum(a, b)\nreturn a + b\nend\nshow sum(2, 3)')
            result = subprocess.run([sys.executable, interpreter, str(program)], capture_output=True, text=True)
            self.assertEqual((result.returncode, result.stdout), (0, '5\n'))
            program.write_text('return 1')
            result = subprocess.run([sys.executable, interpreter, str(program)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('return outside a function', result.stdout)
            self.assertNotIn('Traceback', result.stderr)
            result = subprocess.run([sys.executable, interpreter, str(program) + '.missing'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('file not found', result.stdout)


if __name__ == '__main__':
    unittest.main()
