# RonLang 1.0 release candidate

RonLang is a small, high-level language for web prototypes, APIs, data and
automation. English is the primary language for code, examples and tools.
Spanish syntax aliases remain optional learning aids.

This is **1.0.0rc1**, not a declaration of production stability. Core features
are implemented and tested locally; deployment and platform validation have
separate requirements described below.

## Windows quick start

Use the generated `ron.exe` directly, or run `RonLang-1.0.0rc1-setup.exe` to
install it for your Windows account and add its directory to your user PATH.
Open a new terminal after installation. The executable bundles Python: no
separate Python installation is required for the core language.

```powershell
ron --version
ron new my-website
ron my-website/main.ron
```

Open http://127.0.0.1:8000. The starter includes a homepage, stylesheet,
download and health endpoint. Keep the terminal running; Ctrl+C stops it.
The Windows binary and installer are unsigned. The installer does not require
administrator privileges. The portable package includes `uninstall.ps1`.
The installed copy is also available at `%LOCALAPPDATA%\RonLang\bin\uninstall.ps1`.

For a source installation, use Python 3.10 or newer:

```powershell
python -m pip install .
ron --version
```

Without installation, `python ron.py` accepts the same commands.
The core library has no third-party runtime dependencies. PostgreSQL is optional.

## Your first program

```text
make name = "Ronald"
func greet(person)
    return "Hello, " + person
end
show greet(name)

for number in range(1, 4)
    show number
end
```

Run `ron hello.ron` to execute the original counter example. Blocks end with
`end`; indentation is for readability. No semicolons are required.

## A website with a download

```text
make site = app()
make content = heading("My website")
make content = content + paragraph("Download the welcome file below.")
make content = content + link("Download", "/download")
get(site, "/", page("Downloads", content))
download(site, "/download", "examples/site/files/welcome.txt")
serve(site, 8000)
```

`download` sends the actual bytes with an attachment header. `static(site,
"/assets/", "assets")` serves an existing directory, without directory listings.
Paths are resolved under their configured root; traversal and escaping symlinks
are rejected. File paths are relative to the process working directory, unlike
`use`, which resolves relative to the importing source file.

## Authenticated example

From the repository root in PowerShell:

```powershell
$env:DEMO_PASSWORD = 'choose-a-private-password'
ron examples/site/main.ron
```

The page includes navigation, CSS, a download, sign-in form, profile button and
sign-out form. Passwords are hashed with salted scrypt, never stored as plaintext
in the session. The example uses one configurable demo account; it does not
implement user registration, recovery or permissions.

`sessions(site)` enables server-side sessions with Secure, HttpOnly, SameSite=Lax
cookies, fixed expiry and CSRF checking on state-changing requests. For local
HTTP only, use `sessions(site, false)`. The demo selects this using `COOKIE_SECURE`;
set `COOKIE_SECURE=true` when deploying behind HTTPS. Sessions are in memory and
are lost on restart; they cannot be shared across multiple processes.

Forms automatically fetch `/_ron/csrf` and supply `X-CSRF-Token`. Custom clients
must retain the cookie and send that header themselves. Login rotates the session
identifier and CSRF token; logout invalidates the session. GET handlers must not
perform state-changing actions. Public download/static routes do not require login.

## Language and tools

See [Language reference](docs/language.md) and [Library reference](docs/library.md).

```powershell
ron check main.ron
ron check --json main.ron
ron fmt main.ron
ron test .
```

`check` validates syntax without executing code or importing modules. It does not
prove that variables, external files, databases or routes exist. `fmt` checks the
file then rewrites indentation; `test` executes `test_*.ron` files using `require`.

Errors retain source file and original line, including inside functions/modules:

```text
try
    require 10 < 5
catch error
    show error["message"]
    show error["file"]
    show error["line"]
end
```

Install the generated VSIX from VS Code's **Extensions: Install from VSIX**.
It adds highlighting, snippets, simple completions, saved-file syntax diagnostics
and indentation formatting. Configure `ronlang.executable` if `ron` is not on PATH.
It does not run CLI tools in untrusted workspaces.

## Data

SQLite uses bound values: `sql(db, "INSERT INTO tasks(title) VALUES (?)", [title])`.
`migrate(db, "examples/migrations")` applies ordered `.sql` files once and records
checksums. Each migration is atomic; changed applied files are rejected. End SQL
statements with `;` and do not add transaction-control statements or trailing
standalone comments. Migration files are trusted application code.

For PostgreSQL from source: `python -m pip install '.[postgres]'`. Then call
`postgres(env("DATABASE_URL"), "SELECT %s::text AS name", [name])`.
The Windows build can bundle the adapter if installed at build time. SQL and
PostgreSQL connections are opened per operation, not pooled. SQLite migrations
are not a PostgreSQL migration tool.

Statistics, CSV, vectors, matrices and a basic linear regression model are included;
see `examples/mathematics.ron`. No generative AI or GPU framework is bundled.

## Deployment and validation

[Deployment guide](docs/deployment.md) describes the Docker/Caddy setup,
configuration, persistent data and checks. Nothing is deployed automatically.
[Release checklist](docs/release-checklist.md) separates implemented features
from remaining validation. [Changes](CHANGELOG.md) records the milestones.

```powershell
python -m unittest discover -v
python scripts/benchmark.py
```

The benchmark reports local timings, not a claim that RonLang is faster than
Python or another language. CI is configured for Windows/Linux, multiple Python
versions and a PostgreSQL integration test; its results require an actual CI run.

## Boundaries

The HTTP server is a small threaded server, limited to 32 active workers and
120 requests per minute per client IP per app. It uses a 1 MiB JSON body limit
and a 10-second socket-operation timeout. App handlers run serially to protect
shared interpreter state. These are basic safeguards, not scalability guarantees.
Behind a reverse proxy, requests share the proxy's IP for this rate limit.

RonLang is not a security sandbox: programs can access files and the network.
The language has no static type system or memory-safety verification. It is not
a native systems language, general game engine or large-scale cloud platform.
TLS is provided by the reverse proxy, not by `serve`. Production use needs
application-specific security review, monitoring, backups and load tests.
