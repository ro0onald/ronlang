"""Command-line tools shared by source, pip and frozen installations."""
import argparse
import ast
import json
from pathlib import Path
import sys


def diagnostics(path):
    from ron import normalize, opens_block, parse_expression
    errors, stack = [], []
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines()
    except OSError as error:
        return [{'file': str(path), 'line': 1, 'message': str(error)}]
    for number, original in enumerate(lines, 1):
        line = normalize(original)
        if not line or line.startswith('#'):
            continue
        word, _, rest = line.partition(' ')
        try:
            if word == 'end':
                if not stack:
                    raise ValueError('end without an open block')
                block = stack.pop()
                if block[0] == 'try' and not block[2]:
                    raise ValueError('try needs catch')
                continue
            if word in ('otherwise', 'catch'):
                expected = 'when' if word == 'otherwise' else 'try'
                if not stack or stack[-1][0] != expected or stack[-1][2]:
                    raise ValueError(f'unexpected {word}')
                stack[-1][2] = True
                if word == 'catch' and rest and not rest.isidentifier():
                    raise ValueError('catch needs a variable name')
                continue
            expression = None
            if word == 'func':
                import re
                match = re.fullmatch(r'([A-Za-z_]\w*)\s*\((.*?)\)', rest)
                if not match:
                    raise ValueError('expected func name(parameters)')
                names = [name.strip() for name in match[2].split(',')] if match[2].strip() else []
                if any(not name.isidentifier() for name in names) or len(set(names)) != len(names):
                    raise ValueError('invalid or duplicate parameter')
            elif word == 'make':
                name, separator, expression = rest.partition('=')
                if not separator or not name.strip().isidentifier():
                    raise ValueError('expected make name = value')
            elif word == 'for':
                name, separator, expression = rest.partition(' in ')
                if not separator or not name.isidentifier():
                    raise ValueError('expected for name in collection')
            elif word in ('when', 'while', 'repeat', 'show', 'use', 'require', 'raise'):
                expression = rest
            elif word == 'return':
                if not any(item[0] == 'func' for item in stack):
                    raise ValueError('return outside a function')
                expression = rest or None
            elif word in ('break', 'continue'):
                # A function boundary prevents escaping a caller loop.
                context = [item[0] for item in stack]
                if 'func' in context:
                    context = context[len(context)-1-context[::-1].index('func')+1:]
                if not any(item in ('for', 'while', 'repeat') for item in context):
                    raise ValueError(f'{word} outside a loop')
            elif word != 'try':
                tree = parse_expression(line)
                if not isinstance(tree, ast.Call):
                    raise ValueError('unknown instruction')
                expression = line
            if expression is not None:
                tree = parse_expression(expression.strip())
                allowed = (ast.Expression, ast.Constant, ast.Name, ast.Load, ast.List, ast.Dict,
                           ast.Subscript, ast.UnaryOp, ast.UAdd, ast.USub, ast.Not, ast.BoolOp,
                           ast.And, ast.Or, ast.Call, ast.BinOp, ast.Add, ast.Sub, ast.Mult,
                           ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.Compare, ast.Eq,
                           ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn)
                if any(not isinstance(node, allowed) for node in ast.walk(tree)):
                    raise ValueError('unsupported expression')
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.keywords):
                        raise ValueError('calls require a function name and positional arguments')
            if opens_block(line):
                stack.append([word, number, False])
        except Exception as error:
            errors.append({'file': str(path), 'line': number, 'message': str(error)})
    errors.extend({'file': str(path), 'line': number, 'message': f'{word} without matching end'} for word, number, _ in stack)
    return errors


def format_source(source):
    from ron import normalize, opens_block
    result, depth = [], 0
    for original in source.splitlines():
        text = original.strip()
        normalized = normalize(text)
        word = normalized.partition(' ')[0]
        if word in ('end', 'otherwise', 'catch'):
            depth = max(0, depth-1)
        result.append('    '*depth + text if text else '')
        if opens_block(normalized) or word in ('otherwise', 'catch'):
            depth += 1
    return '\n'.join(result).rstrip() + '\n'


def main(argv=None):
    from ron import __version__, run_file
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog='ron', description='RonLang web application tools')
    parser.add_argument('--version', action='version', version='RonLang ' + __version__)
    sub = parser.add_subparsers(dest='command')
    run = sub.add_parser('run', help='Run a RonLang program')
    run.add_argument('file')
    check = sub.add_parser('check', help='Check syntax without running the program')
    check.add_argument('files', nargs='+')
    check.add_argument('--json', action='store_true')
    fmt = sub.add_parser('fmt', help='Format indentation after checking syntax')
    fmt.add_argument('file')
    new = sub.add_parser('new', help='Create a runnable web starter in a new directory')
    new.add_argument('directory')
    test = sub.add_parser('test', help='Run test_*.ron programs')
    test.add_argument('directory', nargs='?', default='.')
    if argv and not argv[0].startswith('-') and argv[0] not in ('run', 'check', 'fmt', 'new', 'test'):
        argv.insert(0, 'run')
    args = parser.parse_args(argv)
    try:
        if args.command == 'run':
            import logging
            logging.basicConfig(level=logging.INFO, format='%(message)s')
            run_file(args.file)
        elif args.command in ('check', 'fmt'):
            paths = args.files if args.command == 'check' else [args.file]
            errors = [error for path in paths for error in diagnostics(path)]
            if args.command == 'check' and args.json:
                print(json.dumps(errors))
            else:
                for error in errors:
                    print(f"{error['file']}:{error['line']}: {error['message']}")
            if errors:
                return 1
            if args.command == 'fmt':
                path = Path(args.file)
                path.write_text(format_source(path.read_text(encoding='utf-8')), encoding='utf-8')
        elif args.command == 'new':
            from ronstarter import create_project
            create_project(args.directory)
            print(f'Created {args.directory}. Run: ron {Path(args.directory) / "main.ron"}')
        elif args.command == 'test':
            paths = sorted(Path(args.directory).rglob('test_*.ron'))
            if not paths:
                print('No test_*.ron files found')
                return 1
            for path in paths:
                run_file(path)
            print(f'{len(paths)} test programs passed')
        else:
            parser.print_help()
    except (OSError, ValueError) as error:
        print(f'Error: {error}')
        return 1
    return 0
