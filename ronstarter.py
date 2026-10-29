from pathlib import Path

MAIN = '''make site = app()
static(site, "/assets/", "{root}/assets")
download(site, "/download", "{root}/files/welcome.txt")
make content = navigation({{"Home": "/", "Download": "/download"}})
make content = content + heading("Welcome to RonLang")
make content = content + paragraph("Your website is running.")
make content = content + link("Download the example file", "/download")
make content = content + stylesheet("/assets/style.css")
get(site, "/", page("My RonLang website", content))
get(site, "/health", {{"status": "ok"}})
serve(site, integer(env("PORT", "8000")), env("HOST", "127.0.0.1"))
'''


def create_project(directory):
    import json
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / 'assets').mkdir()
    (root / 'files').mkdir()
    # The path is inserted inside string literals; escape it as a JSON string interior.
    escaped = json.dumps(root.as_posix(), ensure_ascii=True)[1:-1]
    (root / 'main.ron').write_text(MAIN.format(root=escaped), encoding='utf-8')
    (root / 'assets/style.css').write_text('a { color: #7dd3fc; margin-right: 1rem; }\n', encoding='utf-8')
    (root / 'files/welcome.txt').write_text('Created with RonLang.\n', encoding='utf-8')
    (root / 'test_home.ron').write_text('require 2 + 2 == 4\n', encoding='utf-8')
    (root / 'README.md').write_text('# My website\n\nRun `ron main.ron`, then open http://127.0.0.1:8000.\n', encoding='utf-8')
