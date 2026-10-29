# RonLang

RonLang is an experimental programming language designed to be easy to learn,
readable, and powerful as it grows.

## Current features

- `show` to display text and values.
- `make` to create variables.
- Arithmetic operations: `+`, `-`, `*`, `/`, `%`.
- Comparisons: `==`, `!=`, `<`, `<=`, `>`, `>=`.
- `when` and `otherwise` for conditions.
- `repeat` for loops.
- `end` to close code blocks.

## Requirements

- Python 3.14 or a compatible version.
- No external Python packages are currently required.

## Run a RonLang program

Open a terminal in this folder and run:

```powershell
py -3.14 ron.py hola.ron
```

## Example

```text
make number = 1

repeat 5
    show number
    make number = number + 1
end

show "Loop finished!"
```

## Project status

RonLang is an early experimental project. Its syntax and features may change.

## Goals

- Make programming easy to learn.
- Keep the language readable.
- Add helpful error messages.
- Support more programming features over time.
- Build editor support and development tools.
