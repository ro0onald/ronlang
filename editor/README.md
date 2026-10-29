# RonLang for VS Code

Install the VSIX with **Extensions: Install from VSIX**. Install the RonLang CLI
and ensure `ron --version` works in a new terminal, or set `ronlang.executable`
to the absolute path of `ron.exe` in your user settings.

Features: English and Spanish keyword highlighting, snippets, simple keyword and
function-name completion, syntax diagnostics on open/save, indentation formatting.
CLI execution is disabled in untrusted workspaces. Completion is not type inference.
Formatting uses a temporary copy; diagnostics inspect the saved file without executing it.
