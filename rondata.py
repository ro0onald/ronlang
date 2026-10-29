"""Small, inspectable data and automation primitives for RonLang."""
import csv
import json
import math
import os
import sqlite3
import statistics
from pathlib import Path
from urllib.request import Request, urlopen


def dot(left, right):
    if len(left) != len(right):
        raise ValueError('dot requires vectors of equal length')
    return math.fsum(a * b for a, b in zip(left, right))


def matrix_multiply(left, right):
    if not left or not right or not left[0] or not right[0]:
        raise ValueError('matrices must not be empty')
    width = len(left[0])
    columns = len(right[0])
    if any(len(row) != width for row in left) or any(len(row) != columns for row in right):
        raise ValueError('matrices must be rectangular')
    if width != len(right):
        raise ValueError('incompatible matrix dimensions')
    return [[dot(row, column) for column in zip(*right)] for row in left]


def fit_line(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError('fit_line needs at least two paired observations')
    xmean, ymean = statistics.mean(xs), statistics.mean(ys)
    variance = math.fsum((x - xmean) ** 2 for x in xs)
    if variance == 0:
        raise ValueError('x values must vary')
    slope = math.fsum((x-xmean)*(y-ymean) for x, y in zip(xs, ys)) / variance
    return {'slope': slope, 'intercept': ymean - slope * xmean}


def read_csv(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    if not rows:
        raise ValueError('write_csv requires at least one row')
    with Path(path).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sql(path, statement, parameters=()):
    # Never interpolate parameter values into SQL text.
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            cursor = connection.execute(statement, parameters)
            return [dict(row) for row in cursor] if cursor.description else cursor.rowcount
    except sqlite3.Error as error:
        raise ValueError(f'database: {error}') from error
    finally:
        connection.close()


def http_json(url, body=None):
    data = None if body is None else json.dumps(body).encode('utf-8')
    request = Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=10) as response:
        content = response.read(1048577)
        if len(content) > 1048576:
            raise ValueError('HTTP response exceeds 1 MiB')
        return json.loads(content)


def valid(value, schema):
    types = {'text': str, 'number': (int, float), 'integer': int,
             'boolean': bool, 'list': list, 'object': dict}
    if not isinstance(value, dict) or not isinstance(schema, dict):
        return False
    for key, kind in schema.items():
        if kind not in types:
            raise ValueError(f'unknown schema type: {kind}')
        if key not in value or not isinstance(value[key], types[kind]):
            return False
        if kind in ('number', 'integer') and isinstance(value[key], bool):
            return False
    return True


def postgres(dsn, statement, parameters=()):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        raise ValueError('PostgreSQL requires: pip install ronlang[postgres]') from None
    try:
        with psycopg.connect(dsn, connect_timeout=5, row_factory=dict_row) as connection:
            cursor = connection.execute(statement, parameters)
            return list(cursor) if cursor.description else cursor.rowcount
    except psycopg.Error as error:
        # Do not expose DSNs or credentials in user-facing error messages.
        raise ValueError('PostgreSQL operation failed; check server configuration and query') from error


def migrate(path, directory):
    """Apply ordered SQLite SQL files once, atomically, recording each version."""
    import hashlib
    connection = sqlite3.connect(path, timeout=5)
    try:
        connection.execute('CREATE TABLE IF NOT EXISTS _ron_migrations (name TEXT PRIMARY KEY, digest TEXT NOT NULL)')
        connection.commit()
        applied = dict(connection.execute('SELECT name, digest FROM _ron_migrations'))
        count = 0
        for file in sorted(Path(directory).glob('*.sql')):
            source = file.read_text(encoding='utf-8')
            digest = hashlib.sha256(source.encode()).hexdigest()
            if file.name in applied:
                if applied[file.name] != digest:
                    raise ValueError(f'applied migration changed: {file.name}')
                continue
            statements, pending = [], ''
            for character in source:
                pending += character
                if character == ';' and sqlite3.complete_statement(pending):
                    statements.append(pending)
                    pending = ''
            if pending.strip():
                # Require a terminator rather than silently ignoring incomplete SQL.
                raise ValueError(f'migration must end each statement with ;: {file.name}')
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                forbidden = (sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT,
                             sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA)
                connection.set_authorizer(lambda action, *args: sqlite3.SQLITE_DENY if action in forbidden else sqlite3.SQLITE_OK)
                try:
                    for statement in statements:
                        connection.execute(statement)
                finally:
                    connection.set_authorizer(None)
                connection.execute('INSERT INTO _ron_migrations VALUES (?, ?)', (file.name, digest))
            count += 1
        return count
    except sqlite3.Error as error:
        raise ValueError(f'migration failed: {error}') from error
    finally:
        connection.close()


def data_builtins():
    return {
        'sum': sum, 'mean': statistics.mean, 'median': statistics.median,
        'stdev': statistics.stdev, 'variance': statistics.variance,
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan, 'log': math.log,
        'exp': math.exp, 'floor': math.floor, 'ceil': math.ceil,
        'pi': lambda: math.pi, 'dot': dot, 'matrix_multiply': matrix_multiply,
        'fit_line': fit_line,
        'predict': lambda model, x: model['slope'] * x + model['intercept'],
        'read_csv': read_csv, 'write_csv': write_csv, 'sql': sql,
        'env': lambda key, default=None: os.environ.get(key, default),
        'http_json': http_json,
        'valid': valid,
        'postgres': postgres, 'migrate': migrate,
        'map': lambda function, values: [function(value) for value in values],
        'filter': lambda function, values: [value for value in values if function(value)],
        'sort': sorted, 'keys': lambda value: list(value),
        'values': lambda value: list(value.values()),
        'join': lambda separator, items: separator.join(items),
        'split': lambda value, separator=None: value.split(separator),
        'replace': lambda value, old, new: value.replace(old, new),
        'contains': lambda collection, value: value in collection,
    }
