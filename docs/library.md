# Standard library reference

Optional positional arguments are shown with their defaults. Calls do not support
named arguments. Errors propagate as RonLang runtime errors unless caught.

## Conversion, strings and collections

- `text(value)`, `number(value)`, `integer(value)` convert values.
- `ask(prompt)` reads terminal input; `length(value)` returns length.
- `range(stop)` or `range(start, stop, step)` excludes `stop`.
- `append(list, value)` mutates a list and returns null.
- `put(collection, key, value)` mutates a collection and returns it.
- `keys(object)`, `values(object)`, `contains(collection, value)`.
- `map(function, values)`, `filter(function, values)`, `sort(values)` return lists.
- `join(separator, items)`, `split(text, separator=null)`, `replace(text, old, new)`.

## Mathematics and data

- `sum(values)`, `min(values)` / `min(a, b)`, `max(values)` / `max(a, b)`.
- `abs(x)`, `round(x, digits=0)`, `sqrt(x)`, `floor(x)`, `ceil(x)`.
- `sin(x)`, `cos(x)`, `tan(x)` use radians; `log(x, base)` also accepts just `x`.
- `exp(x)`, `pi()`, `random(low, high)` (inclusive integers).
- `mean(values)`, `median(values)`, `stdev(values)`, `variance(values)`; sample
  deviation/variance need at least two observations.
- `dot(a, b)`, `matrix_multiply(a, b)` check dimensions.
- `fit_line(xs, ys)` returns `slope` and `intercept`; `predict(model, x)` applies it.
- `read_csv(path)` returns dictionaries with string values.
- `write_csv(path, rows)` uses the first row's keys as columns; rows cannot be empty.
- `sql(path, statement, parameters=[])` executes one SQLite statement with `?`
  placeholders. Queries return dictionary rows; other statements return rowcount.
- `postgres(dsn, statement, parameters=[])` uses PostgreSQL `%s` placeholders
  and the optional psycopg adapter. Never interpolate user data into SQL text.
- `migrate(database, directory)` applies ordered SQLite migrations once.
- `valid(value, schema)` checks required dictionary fields; extra fields are allowed.
  Types: `text`, `number`, `integer`, `boolean`, `list`, `object` (shallow validation).

## Files, configuration and HTTP client

- `read(path)`, `write(path, value)` read/write UTF-8 text.
- `json(value)`, `parse_json(text)` serialize/parse JSON.
- `env(name, default=null)` reads an environment variable.
- `http_json(url, body=null)` makes GET if body is null, otherwise POST JSON;
  response limit 1 MiB, network-operation timeout 10 seconds.

## Web server and frontend

- `app()` creates a web application.
- `get(app, path, handler)`, `post(app, path, handler)` register routes.
- `route(app, method, path, handler)` also supports PUT/PATCH/DELETE.
- Paths can include parameters like `/users/<id>`; literal routes have priority.
- Handlers receive a dictionary with `method`, `path`, `params`, `query`, `headers`
  and `body`. Query values are lists; header names are lowercase.
- `response(body, status=200, headers={})` controls the response. Strings become
  HTML, collections become JSON. Status 204/304 sends no body.
- `serve(app, port=8000, host="127.0.0.1")` blocks until Ctrl+C.
- `download(app, route, filename)` registers an attachment download.
- `static(app, prefix, directory)` registers assets; prefix must end in `/`.
- `page(title, html)`, `heading(text)`, `paragraph(text)`, `card(title, html)`.
- `link(label, url)`, `image(url, alt="")`, `navigation({label: url})`.
- `stylesheet(url)`, `script(url)` reference external asset files.
- `button(label, endpoint, target)` makes GET and shows JSON in `output(target)`.
- `form(label, endpoint, fields, target)` sends JSON POST; all fields are text,
  except a field named `password`, which uses a masked input.
- Text components escape HTML. `page`/`card` accept trusted raw HTML. Link/asset
  URLs allow relative paths and HTTP(S), not script schemes.
- `game(title, width, height, speed=240, color="#55ddff")` embeds the existing
  keyboard-controlled collection game, not a general game engine.

## Sessions and passwords

- `sessions(app, secure=true, ttl=3600)` enables an in-memory session store.
- `password_hash(password)` uses salted scrypt; accepts 8–1024 characters.
  It uses [Python's scrypt implementation](https://docs.python.org/3/library/hashlib.html#hashlib.scrypt).
- `password_verify(password, encoded)` checks a hash with constant-time comparison.
- `session_user(request)` returns the current user value or null.
- `csrf(request)` gets the session's CSRF token.
- `login(request, user)` rotates the session and returns a JSON response.
  The caller must validate credentials first; this function does not authenticate them.
- `logout(request)` invalidates the session and returns a JSON response.

See the README for cookie/CSRF behavior and the single-process limitations.
PostgreSQL value binding follows [psycopg's parameter API](https://www.psycopg.org/psycopg3/docs/basic/params.html).
