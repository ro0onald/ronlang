"""Local baseline only; not a cross-language superiority claim."""
from pathlib import Path
import json
import platform
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ron import run_statements, __version__

source = 'make total = 0\nfor n in range(1000)\nmake total = total + n\nend'.splitlines()


def ron_loop():
    scope = {}
    run_statements(source, scope)
    assert scope['total'] == 499500


def python_loop():
    total = 0
    for n in range(1000):
        total += n
    assert total == 499500


result = {'python': platform.python_version(), 'ronlang': __version__, 'platform': platform.platform(),
          'workload': 'sum integers 0..999 with an explicit loop', 'runs': 7}
for name, function in [('ronlang_seconds', ron_loop), ('python_seconds', python_loop)]:
    function()
    times = []
    for _ in range(7):
        start = time.perf_counter()
        function()
        times.append(time.perf_counter()-start)
    result[name] = statistics.median(times)
print(json.dumps(result, indent=2))
