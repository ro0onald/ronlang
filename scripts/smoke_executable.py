"""Check the distributed executable from a new project and working directory."""
from pathlib import Path
import os
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

executable = str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    subprocess.run([executable, 'new', str(root / 'site')], check=True, timeout=30)
    subprocess.run([executable, 'check', str(root / 'site/main.ron')], check=True, timeout=30)
    with socket.socket() as socket_:
        socket_.bind(('127.0.0.1', 0))
        port = socket_.getsockname()[1]
    environment = dict(os.environ, HOST='127.0.0.1', PORT=str(port))
    process = subprocess.Popen([executable, str(root / 'site/main.ron')], cwd=root, env=environment,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        base = f'http://127.0.0.1:{port}'
        deadline = time.monotonic()+30
        while True:
            try:
                with urlopen(base+'/health', timeout=1) as response:
                    assert response.status == 200
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Executable web server did not start')
                time.sleep(.2)
        with urlopen(base) as response:
            assert b'Your website is running' in response.read()
        with urlopen(base+'/download') as response:
            assert response.read() == (root/'site/files/welcome.txt').read_bytes()
            assert 'attachment' in response.headers['Content-Disposition']
        with urlopen(base+'/assets/style.css') as response:
            assert b'color' in response.read()
        print('Executable HTTP, assets and binary download checks passed')
    finally:
        if os.name == 'nt':
            # A one-file PyInstaller app has a bootloader parent and a child.
            # Stop this exact owned process tree before the parent disappears.
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, check=False)
        else:
            process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
