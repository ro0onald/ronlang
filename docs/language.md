# Language reference

Keywords are case-sensitive. Use ASCII letters or `_` as the first character
of a variable/function name. Prefer English names and avoid keyword/literal names.
Each statement occupies one line. Full-line comments start with `#`.

## Statements

- `make name = expression` creates or updates a variable.
- `show expression` displays a value.
- `func name(a, b)` ... `end` defines a positional-argument function.
- `return expression` returns from the current function; bare `return` is null.
- `when condition` ... optional `otherwise` ... `end` selects a branch.
- `repeat count` ... `end` repeats from 0 to 10000 times.
- `while condition` ... `end` loops while truthy, without an automatic iteration limit.
- `for name in collection` ... `end` iterates a collection.
- `break` exits the innermost loop; `continue` skips to its next iteration.
- `require condition` fails if the expression is falsey.
- `raise expression` creates a catchable runtime error with that message.
- `try` ... `catch name` ... `end` captures runtime errors in a dictionary with
  `message`, `file`, `line`. It does not capture function returns or loop control.
- `use "module.ron"` executes a file relative to the importing file and shares
  its variables/functions with the caller. Cyclic imports are rejected. Modules
  are not namespaces and are re-executed each time they are used.

Each call has local variable bindings. Global values are visible at call time.
`make` inside a function does not rebind caller variables, but lists/dictionaries
passed in are shared mutable objects. Define functions before calling them.
Recursive calls work; depth is limited by Python. Calls use positional arguments
only. Callable values can be passed to `map` and `filter`; assigning a function
to a variable does not currently create a new direct-call name.

## Values and expressions

Numbers: `42`, `3.14`, `-2`. Text: `"hello"` or `'hello'`, with escape sequences.
Booleans: `true`, `false`. Null: `null` (displayed as `None`).
Lists: `[1, 2]`. Dictionaries: `{"name": "Ron"}`.
Access: `items[0]`, `person["name"]`; negative indexes work for lists and text.
There are no slices, comprehensions, attribute calls, classes or keyword arguments.

Arithmetic: `+ - * / // % **`; unary `+` and `-`; parentheses group expressions.
`+` concatenates strings, but does not automatically convert numbers to strings.
Use `text(value)` for conversion. Comparisons: `== != < <= > >= in not in`.
Comparisons can chain: `0 < price <= 100`. Logical `and`, `or` short-circuit
and return operand values; `not` returns a boolean.

## Optional aliases

- `let`, `crear`, `guardar` → `make`.
- `mostrar` → `show`; `function`, `funcion` → `func`.
- `devolver` → `return`; `if`, `si` → `when`; `else`, `sino` → `otherwise`.
- `repetir` → `repeat`; `mientras` → `while`; `para` → `for`.
- `romper` → `break`; `continuar` → `continue`; `fin` → `end`.
- `usar` → `use`; `exigir` → `require`.
- `intentar` → `try`; `capturar` → `catch`; `fallar` → `raise`.
- `verdadero`, `falso`, `nulo` → `true`, `false`, `null`.
- `y`, `o`, `no` are contextual logical aliases. Prefer `and/or/not` in complex expressions.
- `crear name es value`, `let name be value`, `make name is value` allow assignment
  connectors. `para name en collection` allows the loop connector `en`.

Aliases translate tokens, not quoted strings. Library function names remain English,
except `descarga`, which is retained as an alias of `download`.
