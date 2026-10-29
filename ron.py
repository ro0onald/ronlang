
from pathlib import Path
import ast
import operator
import re
import sys
from ronlib import builtins

__version__ = "0.3.0"


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class Function:
    def __init__(self, parameters, body, variables, functions):
        self.parameters = parameters
        self.body = body
        self.variables = variables
        self.functions = functions

    def __call__(self, *arguments):
        if len(arguments) != len(self.parameters):
            raise ValueError(f"expected {len(self.parameters)} arguments, got {len(arguments)}")
        local = dict(self.variables)
        local.update(zip(self.parameters, arguments))
        try:
            run_statements(self.body, local, dict(self.functions), True)
        except _Return as result:
            return result.value
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

        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left = evaluate(node.left)
            right = evaluate(node.comparators[0])
            if type(node.ops[0]) in compare_ops:
                return compare_ops[type(node.ops[0])](left, right)

        raise ValueError("invalid expression")

    return evaluate(ast.parse(expression, mode="eval").body)


def find_block_end(lines, start):
    depth = 1

    for index in range(start, len(lines)):
        line = lines[index].strip()

        if line.startswith(("repeat ", "when ", "func ", "while ", "for ")):
            depth += 1
        elif line == "end":
            depth -= 1
            if depth == 0:
                return index

    raise ValueError("block without matching end")


def run_statements(lines, variables, functions=None, in_function=False):
    functions = builtins() if functions is None else functions
    i = 0

    while i < len(lines):
        line_number = i + 1
        line = lines[i].strip()
        i += 1

        if not line or line.startswith("#"):
            continue

        if line.startswith("func "):
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
                    run_statements(block, variables, functions, in_function)
            else:
                while calculate(line[6:], variables, functions):
                    run_statements(block, variables, functions, in_function)
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
                run_statements(block, variables, functions, in_function)

            i = end_index + 1

        elif line.startswith("when "):
            end_index = find_block_end(lines, i)
            block_lines = lines[i:end_index]
            otherwise_index = None
            depth = 0
            for j, item in enumerate(block_lines):
                item = item.strip()
                if item.startswith(("repeat ", "when ", "func ", "while ", "for ")):
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
            run_statements(true_block if result else false_block, variables, functions, in_function)
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


def run_file(filename):
    path = Path(filename)

    if not path.exists():
        print(f"Error: file not found: {filename}")
        sys.exit(1)

    try:
        run_statements(path.read_text(encoding="utf-8").splitlines(), {})
    except (ValueError, SyntaxError, TypeError, ArithmeticError, RecursionError, OSError, LookupError) as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) > 1 else "hola.ron"
    run_file(filename)
