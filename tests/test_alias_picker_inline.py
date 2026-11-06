"""The alias picker run for real in inline mode, in a pseudo-terminal.

Pilot runs headless, not inline, so it cannot see inline-only layout. Textual pads an inline screen
with a blank row above and below; with the widget sized to terminal height − 1 that pushed the key
bar off the bottom. This draws the real thing and checks the first and last rows are on screen.
"""

import os
import re
import select
import subprocess
import sys
import time

import pytest

pty = pytest.importorskip("pty")
fcntl = pytest.importorskip("fcntl")
termios = pytest.importorskip("termios")

PROGRAM = """
from shelley.ui.alias_picker import AliasPickerApp
names = [f"tool{i:02d}" for i in range(40)]
app = AliasPickerApp([{"name": n, "command": f"/usr/local/bin/{n}"} for n in names], "samtools", "1.21")
app.run(inline=True)
"""
ANSI = re.compile(r"\x1b\[[0-9;?<>=]*[A-Za-z]|\x1b[()][A-Z0-9]|\x1b[=>]")


def run_inline(width: int, height: int, seconds: float = 4.0) -> str:
    import struct

    pid, fd = pty.fork()
    if pid == 0:  # child: run the picker attached to the pseudo-terminal
        os.environ["TERM"] = "xterm-256color"
        os.execvp(sys.executable, [sys.executable, "-c", PROGRAM])
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", height, width, 0, 0))
    out = b""
    end = time.time() + seconds
    try:
        while time.time() < end:
            ready, _, _ = select.select([fd], [], [], 0.05)
            if ready:
                out += os.read(fd, 65536)
                if b"Esc Exit" in ANSI.sub("", out.decode(errors="replace")).encode():
                    break
        os.write(fd, b"\x03")  # Ctrl+C
        time.sleep(0.5)
    except OSError:
        pass
    finally:
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass
        os.waitpid(pid, 0)
        os.close(fd)
    return ANSI.sub("", out.decode(errors="replace"))


@pytest.mark.timeout(30)
@pytest.mark.parametrize(("width", "height"), [(80, 24), (120, 40), (80, 23)])
def test_inline_widget_shows_title_and_key_bar(width, height):
    screen = run_inline(width, height)
    assert "Choose aliases — samtools 1.21" in screen
    assert "Esc Exit" in screen  # the key bar, the widget's last row


def test_subprocess_import_is_clean():
    # Guard the test program itself, so a failure above is about layout, not an import error.
    subprocess.run([sys.executable, "-c", "import shelley.ui.alias_picker"], check=True)
