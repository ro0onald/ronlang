"""File responses keep filesystem paths confined to a configured directory."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileResponse:
    root: Path
    relative: str
    attachment: bool = False

    def path(self):
        root = self.root.resolve()
        path = (root / self.relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise FileNotFoundError('file is missing or outside the configured directory')
        return path


def download(app, route, filename):
    path = Path(filename).resolve()
    if not path.is_file():
        raise ValueError(f'download file not found: {path}')
    app.add('GET', route, FileResponse(path.parent, path.name, True))


def static(app, prefix, directory):
    if not prefix.startswith('/') or not prefix.endswith('/'):
        raise ValueError('static prefix must start and end with /')
    root = Path(directory).resolve()
    if not root.is_dir():
        raise ValueError('static directory does not exist')
    app.static_routes[prefix] = root
