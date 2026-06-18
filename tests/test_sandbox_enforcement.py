import os
import subprocess
import sys

def test_sandbox_subprocess_blocked():
    """Verify that subprocess execution is blocked when configured."""
    code = """
import os
from runtime.kei_sandbox import enable_sandbox
import subprocess
import tempfile

with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
    f.write('permissions:\\n  execution:\\n    allow_subprocess: false')
    config_path = f.name

try:
    enable_sandbox(config_path=config_path)
    subprocess.run(['echo', 'hello'], capture_output=True)
    print('FAILED: subprocess allowed')
except PermissionError as e:
    print(f'SUCCESS: {e}')
finally:
    os.unlink(config_path)
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "src"})
    assert "SUCCESS: KEI Sandbox: subprocess execution is blocked." in result.stdout

def test_sandbox_network_blocked():
    """Verify that unauthorized network connections are blocked."""
    code = """
import os
import socket
from runtime.kei_sandbox import enable_sandbox
import tempfile

with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
    f.write('permissions:\\n  network:\\n    allow: [\"127.0.0.1\"]')
    config_path = f.name

try:
    enable_sandbox(config_path=config_path)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('8.8.8.8', 53))
    print('FAILED: network allowed')
except PermissionError as e:
    print(f'SUCCESS: {e}')
finally:
    os.unlink(config_path)
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "src"})
    assert "SUCCESS: KEI Sandbox: Network connection to 8.8.8.8 is blocked." in result.stdout

def test_sandbox_write_blocked():
    """Verify that unauthorized file writes are blocked."""
    code = """
import os
from runtime.kei_sandbox import enable_sandbox
import tempfile

with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
    f.write('permissions:\\n  filesystem:\\n    allow_write: [\"/tmp/allowed\"]')
    config_path = f.name

try:
    enable_sandbox(config_path=config_path)
    with open('/tmp/blocked_file.txt', 'w') as f:
        f.write('data')
    print('FAILED: write allowed')
except PermissionError as e:
    print(f'SUCCESS: {e}')
finally:
    os.unlink(config_path)
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "src"})
    assert "SUCCESS: KEI Sandbox: Write access to /tmp/blocked_file.txt is blocked." in result.stdout
