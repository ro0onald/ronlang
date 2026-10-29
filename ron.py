
from pathlib import Path
import ast
import operator
import re
import sys


def calculate(expression, variables):
    binary_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
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
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value

        if isinstance(node, ast.Name):
            if node.id in variables:
                return variables[node.id]
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

        if line.startswith(("repeat ", "when ")):
            depth += 1
        elif line == "end":
            depth -= 1
            if depth == 0:
                return index

    raise ValueError("block without matching end")


def run_statements(lines, variables):
    i = 0

    while i < len(lines):
        line_number = i + 1
        line = lines[i].strip()
        i += 1

        if not line:
            continue

        if line.startswith("repeat "):
            end_index = find_block_end(lines, i)
            block = lines[i:end_index]
            count = calculate(line[7:].strip(), variables)

            if not isinstance(count, int) or count < 0 or count > 10000:
                raise ValueError(
                    f"line {line_number}: repeat needs an integer from 0 to 10000"
                )

            for _ in range(count):
                run_statements(block, variables)

            i = end_index + 1

        elif line.startswith("when "):
            end_index = find_block_end(lines, i)
            block_lines = lines[i:end_index]
            otherwise_index = next(
                (
                    j for j, item in enumerate(block_lines)
                    if item.strip() == "otherwise"
                ),
                None,
            )

            if otherwise_index is None:
                true_block = block_lines
                false_block = []
            else:
                true_block = block_lines[:otherwise_index]
                false_block = block_lines[otherwise_index + 1:]

            result = calculate(line[5:].strip(), variables)
            run_statements(true_block if result else false_block, variables)
            i = end_index + 1

        elif line.startswith("show "):
            value = line[5:].strip()
            if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
                print(value[1:-1])
            else:
                print(calculate(value, variables))

        elif line.startswith("make "):
            match = re.fullmatch(r'make\s+([A-Za-z_]\w*)\s*=\s*(.+)', line)
            if not match:
                raise ValueError(
                    f"line {line_number}: expected make name = value"
                )

            name, value = match.groups()
            value = value.strip()

            if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
                variables[name] = value[1:-1]
            else:
                variables[name] = calculate(value, variables)

        elif line == "end":
            raise ValueError(f"line {line_number}: end without an open block")

        elif line == "otherwise":
            raise ValueError(f"line {line_number}: otherwise without when")

        else:
            raise ValueError(
                f"line {line_number}: unknown instruction: {line}"
            )


def run_file(filename):
    path = Path(filename)

    if not path.exists():
        print(f"Error: file not found: {filename}")
        sys.exit(1)

    try:
        run_statements(path.read_text(encoding="utf-8").splitlines(), {})
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError) as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) > 1 else "hola.ron"
    run_file(filename)
