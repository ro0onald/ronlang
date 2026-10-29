# RonLang 0.3 — Web y juegos 2D

RonLang is an experimental programming language designed to be easy to learn
and readable as it grows.

## Requirements and execution

Python 3.10 or newer; no external packages required. In this folder, run:

```powershell
python ron.py hola.ron
```

If you use the Windows Python launcher, use `py ron.py hola.ron`.
Without a filename, RonLang runs `hola.ron` in the current directory.

## Syntax

- `show expression` displays a value.
- `make name = expression` creates or updates a variable.
- Numbers support `+`, `-`, `*`, `/`, `%`, parentheses and comparisons
  (`==`, `!=`, `<`, `<=`, `>`, `>=`).
- Quoted strings support concatenation with `+`. Both operands must be strings;
  numbers are not automatically converted to text.
- `when expression`, optional `otherwise`, and `end` select a branch.
- `repeat expression` and `end` repeat a block 0 to 10000 times.
- `func name(parameters)` and `end` define a function.
- `return expression` exits the current function, including from nested blocks.
  Bare `return`, or reaching the end, returns `None`.
- Functions can be called as statements or inside expressions, including nested
  calls and recursion. Arguments are positional and must match the parameter count.

Indentation is for readability; `end` closes each block. Functions must be defined
before they are called. Each call has local variables: parameters and `make`
assignments inside the function do not change the caller's variables. Functions
can read variables from the scope where they were defined, using their values at
call time. Function definitions inside a call stay local to that call.

## Functions and strings

```text
func greet(name)
    show "Hello, " + name
end

func add(a, b)
    return a + b
end

greet("Ronald")
make result = add(10, 20)
show result
show add(add(1, 2), 3) * 2
```

Output:

```text
Hello, Ronald
30
12
```

## Conditions and loops

```text
make number = 1
repeat 5
    when number > 3
        show "Large"
    otherwise
        show number
    end
    make number = number + 1
end
show "Loop finished!"
```

## Automated tests

From the project folder:

```powershell
python -m unittest discover -v
```

Tests cover the original example, arithmetic, comparisons, nested conditions,
functions, recursion, local scope, returns from loops, string concatenation,
invalid programs, and command-line execution and errors.

## Project status

RonLang is an early experimental project. Syntax and features may change.
It is not a security sandbox for untrusted programs.

## Novedades 0.3: web y juegos

Ejecuta desde esta carpeta (Ctrl+C para detener el servidor):

```powershell
python ron.py examples/web.ron
```

Abre http://127.0.0.1:8000. El botón consulta una API JSON escrita en RonLang.
`GET /api/hello` devuelve un saludo; `POST /api/echo` devuelve el cuerpo JSON recibido.
Para probar el juego, detén primero el servidor anterior y ejecuta:

```powershell
python ron.py examples/game.ron
```

Abre la misma dirección. Usa flechas o WASD para recoger cuadrados dorados.
`game(title, width, height, speed, color)` genera esa escena 2D configurable;
no es todavía un motor general con scripting de físicas, niveles o escenas.

### Web en pocas instrucciones

```text
make site = app()
func welcome(request)
    return {"message": "Hola", "ok": true}
end
get(site, "/api", welcome)
get(site, "/", page("Mi web", heading("Bienvenido")))
serve(site, 8000)
```

`get` y `post` reciben una aplicación, ruta exacta y función (o contenido fijo).
La función recibe un diccionario con `method`, `path`, `query` y `body`.
Los parámetros de consulta son listas: `request["query"]["name"][0]`.
Los cuerpos POST deben ser JSON (máximo 1 MiB). Las cadenas se envían como HTML;
otros valores, como JSON. Rutas desconocidas devuelven 404.

Frontend: `page(title, content)`, `heading(text)`, `paragraph(text)`,
`button(label, endpoint, target)` y `output(target)`. El botón muestra el JSON
de un GET en el área indicada. Los componentes de texto escapan HTML; `page`
recibe contenido HTML de confianza y permite añadir CSS y JavaScript propios.
El servidor usa solo la interfaz local. Es para desarrollo; aún no ofrece
autenticación, HTTPS, base de datos ni despliegue de producción.

### Lenguaje y biblioteca

- `# comentario` en su propia línea; `true`, `false`, `null`.
- Listas `[1, 2]`, diccionarios `{"name": "Ron"}`, acceso `items[0]`.
- `for name in collection ... end` y `while condition ... end`.
- `and`, `or` (cortocircuito), `not`, números negativos, `**` y `//`.
- Conversión: `text(value)`, `number(value)`, `integer(value)`.
- Colecciones: `length(value)`, `range(stop)` o `range(start, stop, step)`,
  `append(list, value)`, `put(collection, key, value)`.
- Matemáticas: `abs`, `round`, `min`, `max`, `sqrt`, `random(min, max)` inclusivo.
- Entrada y archivos UTF-8: `ask(prompt)`, `read(path)`, `write(path, text)`.
- JSON: `json(value)`, `parse_json(text)`.

`examples/basics.ron` demuestra colecciones y bucles. Los bucles `while` no
tienen límite automático. No hay todavía `break`, importaciones, clases,
editor visual, 3D, exportación nativa, multijugador ni motor de físicas.
Esta versión es una base funcional, no la finalización de todas esas capacidades.
