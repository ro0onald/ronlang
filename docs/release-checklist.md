# Release candidate validation

Implemented milestones:

- 0.6: streaming downloads, static assets, source errors, standalone Windows build.
- 0.7: catchable runtime errors, relative modules, CLI syntax checking/formatting.
- 0.8: JSON forms, server-side sessions, CSRF, password hashing, SQLite migrations,
  optional PostgreSQL adapter.
- 0.9: starter generator, editor extension, container/proxy configuration, CI and
  reproducible build scripts.
- 1.0 candidate: integration tests and compatibility documentation.

Before declaring a stable 1.0 release:

- Run the full configured Windows/Linux/Python CI matrix.
- Run PostgreSQL integration against a real server.
- Verify Docker Compose, real-domain HTTPS and secure-cookie behavior on staging.
- Exercise the installer on a clean Windows user profile and sign the binaries.
- Exercise VS Code features interactively; package installation alone is not
  proof of every editor feature.
- Run realistic concurrent load, recovery and application security tests.
- Validate symlink rejection on a platform that permits creating the test link.

The local test output and build artifacts identify what was actually verified.
Do not label skipped integrations as passing tests.
