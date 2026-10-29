import os
import unittest
from rondata import postgres


@unittest.skipUnless(os.environ.get('RON_TEST_POSTGRES'), 'PostgreSQL integration requires RON_TEST_POSTGRES')
class PostgreSQLTests(unittest.TestCase):
    def test_parameter_binding_and_rows(self):
        rows = postgres(os.environ['RON_TEST_POSTGRES'], 'SELECT %s::text AS value', ["x'; DROP TABLE users; --"])
        self.assertEqual(rows, [{'value': "x'; DROP TABLE users; --"}])
