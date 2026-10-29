# Deployment guide

The included deployment is a starting configuration, not a validated production
service. Test it on a staging host before exposing real users or private data.

## Local container

```sh
docker build -t ronlang:1.0-rc .
docker run --rm -p 127.0.0.1:8000:8000 -e DEMO_PASSWORD="your-private-password" -e COOKIE_SECURE=false ronlang:1.0-rc
```

The image runs without root privileges. Open http://127.0.0.1:8000.
No database is used by the authenticated demo. For the SQLite tasks demo, override
the command and mount `/data`, setting `RON_DATABASE=/data/tasks.sqlite3`.

## HTTPS reverse proxy

On a host with Docker Compose, a domain pointing to it and inbound ports 80/443:

1. Set `DOMAIN` and `DEMO_PASSWORD` in the host environment. Do not commit secrets.
2. Run `docker compose -f deploy/compose.yml up --build -d`.
3. Check `https://YOUR_DOMAIN/health`, login/logout, asset and download behavior.
4. Read `docker compose -f deploy/compose.yml logs` for service/proxy output.

Caddy obtains TLS certificates when its domain/network prerequisites are met.
Its image uses the `2-alpine` tag; pin a tested digest for reproducible releases.
The proxy configuration is not executed in this development session.

## Operations

- `HOST`, `PORT`, `COOKIE_SECURE`, `DEMO_PASSWORD` configure the example.
- Sessions are in process memory. Restarts sign everyone out. Do not run multiple
  app replicas until a shared session store is implemented.
- The server serializes app handlers. Load-test realistic requests before setting
  capacity expectations. Proxy clients share its per-IP rate limit.
- SQLite is local storage. Back up the database consistently; do not copy a live
  database blindly. PostgreSQL needs its own credentials, backups and migration plan.
- HTTP logs report method/status, excluding cookies and query values. Application
  errors can include developer messages; review log access and retention.
- Keep downloads/static roots read-only to untrusted users. The path checks are
  not an OS-level file-access sandbox and do not defend against a local attacker
  racing filesystem changes while the server opens a file.
- Set Secure cookies for HTTPS. Do not use the local demo password configuration
  as a multi-user identity system. Add authorization per resource and a proper
  account lifecycle for real applications.

No cloud resources, DNS changes or deployment are performed by the build scripts.
