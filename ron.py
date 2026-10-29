
from pathlib import Path
import ast
import operator
import re
import sys
import io
import tokenize
from contextvars import ContextVar
from functools import lru_cache
from ronlib import builtins

__version__ = "1.0.0rc1"
_directory = ContextVar("directory", default=None)
_imports = ContextVar("imports", default=())


def normalize(line):
    aliases = {"mostrar": "show", "crear": "make", "guardar": "make",
               "funcion": "func", "devolver": "return", "si": "when",
               "sino": "otherwise", "repetir": "repeat", "mientras": "while",
               "para": "for", "fin": "end", "usar": "use",
               "exigir": "require", "romper": "break", "continuar": "continue", "let": "make", "function": "func",
               "if": "when", "else": "otherwise", "intentar": "try", "capturar": "catch", "fallar": "raise"}
    pieces = line.strip().split(maxsplit=1)
    if not pieces:
        return ""
    first = aliases.get(pieces[0], pieces[0])
    rest = pieces[1] if len(pieces) == 2 else ""
    if first == "make":
        rest = re.sub(r"^([A-Za-z_]\w*)\s+(?:es|is|be)\s+", r"\1 = ", rest)
    if first == "for":
        rest = re.sub(r"^([A-Za-z_]\w*)\s+en\s+", r"\1 in ", rest)
    return first + (" " + rest if rest else "")


def expression_aliases(expression):
    aliases = {"verdadero": "true", "falso": "false", "nulo": "null"}
    # Only tokens change: quoted text always stays intact.
    tokens = list(tokenize.generate_tokens(io.StringIO(expression).readline))
    result = []
    previous_ends_value = False
    for index, token in enumerate(tokens):
        value = token.string
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        next_starts_value = following is not None and (following.type in (
            tokenize.NAME, tokenize.NUMBER, tokenize.STRING) or following.string in ('(', '[', '{'))
        if token.type == tokenize.NAME:
            value = aliases.get(value, value)
            if value in ('y', 'o') and previous_ends_value and next_starts_value:
                value = {'y': 'and', 'o': 'or'}[value]
            elif value == 'no' and not previous_ends_value and next_starts_value:
                value = 'not'
        result.append((token.type, value))
        previous_ends_value = (token.type in (tokenize.NAME, tokenize.NUMBER, tokenize.STRING)
                               and value not in ('and', 'or', 'not', 'in')) or value in (')', ']', '}')
    return tokenize.untokenize(result)


@lru_cache(maxsize=2048)
def parse_expression(expression):
    return ast.parse(expression_aliases(expression), mode="eval").body



class RonError(ValueError):
    """A user-facing error retaining the original source location."""
    def __init__(self, message, source="<program>", line=1):
        self.message, self.source, self.line = str(message), str(source), line
        super().__init__(f"{self.source}:{self.line}: {self.message}")


class SourceLines(list):
    def __init__(self, values, source="<program>", offset=0):
        super().__init__(values)
        self.source, self.offset = str(source), offset

    def __getitem__(self, index):
        value = super().__getitem__(index)
        if isinstance(index, slice):
            start, _, step = index.indices(len(self))
            if step != 1:
                raise ValueError("source slices must be contiguous")
            return SourceLines(value, self.source, self.offset + start)
        return value


def opens_block(line):
    return line == "try" or line.startswith(("repeat ", "when ", "func ", "while ", "for "))


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class Function:
    def __init__(self, parameters, body, variables, functions):
        self.directory = _directory.get()
        self.parameters = parameters
        self.body = body
        self.variables = variables
        self.functions = functions

    def __call__(self, *arguments):
        if len(arguments) != len(self.parameters):
            raise ValueError(f"expected {len(self.parameters)} arguments, got {len(arguments)}")
        local = dict(self.variables)
        local.update(zip(self.parameters, arguments))
        token = _directory.set(self.directory)
        try:
            run_statements(self.body, local, dict(self.functions), True)
        except _Return as result:
            return result.value
        finally:
            _directory.reset(token)
        return None


def calculate(expression, variables, functions=None):
    functions = builtins() if functions is None else functions
    binary_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.FloorDiv: operator.floordiv,
    }
    compare_ops = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b,
    }

    def evaluate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float, str, bool, type(None)):
            return node.value

        if isinstance(node, ast.List):
            return [evaluate(item) for item in node.elts]
        if isinstance(node, ast.Dict):
            if any(key is None for key in node.keys):
                raise ValueError("dictionary unpacking is not supported")
            return {evaluate(k): evaluate(v) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.Subscript):
            return evaluate(node.value)[evaluate(node.slice)]
        if isinstance(node, ast.UnaryOp):
            value = evaluate(node.operand)
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return +value
            if isinstance(node.op, ast.Not):
                return not value
        if isinstance(node, ast.BoolOp):
            result = evaluate(node.values[0])
            for item in node.values[1:]:
                if isinstance(node.op, ast.And) and not result:
                    return result
                if isinstance(node.op, ast.Or) and result:
                    return result
                result = evaluate(item)
            return result
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.keywords:
                raise ValueError("invalid function call")
            if node.func.id not in functions:
                raise ValueError(f"unknown function: {node.func.id}")
            return functions[node.func.id](*(evaluate(arg) for arg in node.args))

        if isinstance(node, ast.Name):
            if node.id in ("true", "false", "null"):
                return {"true": True, "false": False, "null": None}[node.id]
            if node.id in variables:
                return variables[node.id]
            if node.id in functions:
                return functions[node.id]
            raise ValueError(f"unknown variable: {node.id}")

        if isinstance(node, ast.BinOp) and type(node.op) in binary_ops:
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Div) and right == 0:
                raise ValueError("division by zero")
            return binary_ops[type(node.op)](left, right)

        if isinstance(node, ast.Compare):
            left = evaluate(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = evaluate(comparator)
                if type(op) not in compare_ops:
                    raise ValueError("unsupported comparison")
                if not compare_ops[type(op)](left, right):
                    return False
                left = right
            return True

        raise ValueError("invalid expression")

    return evaluate(parse_expression(expression))


def find_block_end(lines, start):
    depth = 1

    for index in range(start, len(lines)):
        line = normalize(lines[index])

        if opens_block(line):
            depth += 1
        elif line == "end":
            depth -= 1
            if depth == 0:
                return index

    raise ValueError("block without matching end")


def run_statements(lines, variables, functions=None, in_function=False, in_loop=False):
    functions = builtins() if functions is None else functions
    lines = lines if isinstance(lines, SourceLines) else SourceLines(lines)
    i = 0

    while i < len(lines):
        line_number = lines.offset + i + 1
        line = normalize(lines[i])
        i += 1

        if not line or line.startswith("#"):
            continue

        try:
            if line in ("break", "continue"):
                if not in_loop:
                    raise ValueError(f"line {line_number}: {line} outside a loop")
                raise _Break() if line == "break" else _Continue()

            elif line.startswith("use "):
                filename = calculate(line[4:], variables, functions)
                if not isinstance(filename, str):
                    raise ValueError("use expects a filename string")
                path = ((_directory.get() or Path.cwd()) / filename).resolve()
                if path in _imports.get():
                    raise ValueError(f"circular module: {path}")
                directory_token = _directory.set(path.parent)
                imports_token = _imports.set(_imports.get() + (path,))
                try:
                    run_statements(SourceLines(path.read_text(encoding="utf-8").splitlines(), path), variables, functions)
                finally:
                    _directory.reset(directory_token)
                    _imports.reset(imports_token)

            elif line == "try":
                end_index = find_block_end(lines, i)
                depth, catch_index = 0, None
                error_name = "error"
                for index in range(i, end_index):
                    item = normalize(lines[index])
                    if opens_block(item):
                        depth += 1
                    elif item == "end":
                        depth -= 1
                    elif depth == 0 and (item == "catch" or item.startswith("catch ")):
                        if catch_index is not None:
                            raise ValueError("only one catch is allowed")
                        catch_index = index
                        error_name = item[5:].strip() or "error"
                        if not re.fullmatch(r"[A-Za-z_]\w*", error_name):
                            raise ValueError("catch requires a variable name")
                if catch_index is None:
                    raise ValueError("try needs catch")
                try:
                    run_statements(lines[i:catch_index], variables, functions, in_function, in_loop)
                except RonError as error:
                    variables[error_name] = {"message": error.message, "file": error.source, "line": error.line}
                    run_statements(lines[catch_index+1:end_index], variables, functions, in_function, in_loop)
                i = end_index + 1

            elif line.startswith("raise "):
                raise ValueError(calculate(line[6:], variables, functions))

            elif line.startswith("require "):
                if not calculate(line[8:], variables, functions):
                    raise ValueError(f"line {line_number}: requirement failed: {line[8:]}")

            elif line.startswith("func "):
                match = re.fullmatch(r"func\s+([A-Za-z_]\w*)\s*\((.*?)\)", line)
                if not match:
                    raise ValueError(f"line {line_number}: expected func name(parameters)")
                name, parameters = match.groups()
                parameters = [item.strip() for item in parameters.split(",")] if parameters.strip() else []
                if any(not re.fullmatch(r"[A-Za-z_]\w*", item) for item in parameters):
                    raise ValueError("invalid parameter name")
                if len(set(parameters)) != len(parameters):
                    raise ValueError("duplicate parameter name")
                end_index = find_block_end(lines, i)
                functions[name] = Function(parameters, lines[i:end_index], variables, functions)
                i = end_index + 1

            elif line == "return" or line.startswith("return "):
                if not in_function:
                    raise ValueError(f"line {line_number}: return outside a function")
                raise _Return(calculate(line[6:].strip(), variables, functions) if line[6:].strip() else None)

            elif line.startswith(("while ", "for ")):
                end_index = find_block_end(lines, i)
                block = lines[i:end_index]
                if line.startswith("for "):
                    match = re.fullmatch(r"for\s+([A-Za-z_]\w*)\s+in\s+(.+)", line)
                    if not match:
                        raise ValueError("expected for name in collection")
                    name, expression = match.groups()
                    for value in calculate(expression, variables, functions):
                        variables[name] = value
                        try:
                            run_statements(block, variables, functions, in_function, True)
                        except _Continue:
                            continue
                        except _Break:
                            break
                else:
                    while calculate(line[6:], variables, functions):
                        try:
                            run_statements(block, variables, functions, in_function, True)
                        except _Continue:
                            continue
                        except _Break:
                            break
                i = end_index + 1

            elif line.startswith("repeat "):
                end_index = find_block_end(lines, i)
                block = lines[i:end_index]
                count = calculate(line[7:].strip(), variables, functions)

                if not isinstance(count, int) or count < 0 or count > 10000:
                    raise ValueError(
                        f"line {line_number}: repeat needs an integer from 0 to 10000"
                    )

                for _ in range(count):
                    try:
                        run_statements(block, variables, functions, in_function, True)
                    except _Continue:
                        continue
                    except _Break:
                        break

                i = end_index + 1

            elif line.startswith("when "):
                end_index = find_block_end(lines, i)
                block_lines = lines[i:end_index]
                otherwise_index = None
                depth = 0
                for j, item in enumerate(block_lines):
                    item = normalize(item)
                    if opens_block(item):
                        depth += 1
                    elif item == "end":
                        depth -= 1
                    elif item == "otherwise" and depth == 0:
                        if otherwise_index is not None:
                            raise ValueError("multiple otherwise branches")
                        otherwise_index = j

                if otherwise_index is None:
                    true_block = block_lines
                    false_block = []
                else:
                    true_block = block_lines[:otherwise_index]
                    false_block = block_lines[otherwise_index + 1:]

                result = calculate(line[5:].strip(), variables, functions)
                run_statements(true_block if result else false_block, variables, functions, in_function, in_loop)
                i = end_index + 1

            elif line.startswith("show "):
                value = line[5:].strip()
                print(calculate(value, variables, functions))

            elif line.startswith("make "):
                match = re.fullmatch(r'make\s+([A-Za-z_]\w*)\s*=\s*(.+)', line)
                if not match:
                    raise ValueError(
                        f"line {line_number}: expected make name = value"
                    )

                name, value = match.groups()
                value = value.strip()

                variables[name] = calculate(value, variables, functions)

            elif line == "end":
                raise ValueError(f"line {line_number}: end without an open block")

            elif line == "otherwise":
                raise ValueError(f"line {line_number}: otherwise without when")

            else:
                try:
                    expression = ast.parse(line, mode="eval").body
                except SyntaxError:
                    raise ValueError(f"line {line_number}: unknown instruction: {line}") from None
                if not isinstance(expression, ast.Call):
                    raise ValueError(f"line {line_number}: unknown instruction: {line}")
                calculate(line, variables, functions)
        except RonError:
            raise
        except (ValueError, SyntaxError, TypeError, ArithmeticError, RecursionError, OSError, LookupError, tokenize.TokenError) as error:
            message = str(error)
            if message.startswith("unknown variable:"):
                message += " (define it with make or crear before using it)"
            raise RonError(message, lines.source, line_number) from None



def run_file(filename):
    path = Path(filename)

    if not path.exists():
        print(f"Error: file not found: {filename}")
        sys.exit(1)

    directory_token = _directory.set(path.resolve().parent)
    imports_token = _imports.set((path.resolve(),))
    try:
        run_statements(SourceLines(path.read_text(encoding="utf-8").splitlines(), path), {})
    except (ValueError, SyntaxError, TypeError, ArithmeticError, RecursionError, OSError, LookupError, tokenize.TokenError) as error:
        print(f"Error in {filename}: {error}")
        sys.exit(1)
    finally:
        _directory.reset(directory_token)
        _imports.reset(imports_token)


def main():
    from roncli import main as cli_main
    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
