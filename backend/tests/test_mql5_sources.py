"""Guards for the two MQL5 mistakes the compiler does not stop.

The advisors are not covered by the Python suite — they run inside the
terminal — so a mistake in them surfaces as "the bridge received nothing"
with no traceback anywhere. Two shapes have already happened:

* `char buf[]` passed to SocketSend/SocketRead. This one the compiler does
  reject, and it blocked all eight advisors at once because the buffers live
  in the shared header. Pinned anyway: the fix is a single letter and is easy
  to undo while editing nearby code.

* `return StringTrimRight(s)`. StringTrimRight trims in place and returns the
  NUMBER of characters it removed, so this returns "1" where the caller
  expects the server's JSON. The compiler only warns — "implicit conversion
  from 'int' to 'string'" — and an .ex5 is produced, connects, sends, reads,
  and then throws the answer away.

Both are source-level checks on purpose: they must hold for every advisor,
including ones added later, and they must not need a terminal to run.
"""
from pathlib import Path

import pytest

MT5_DIR = Path(__file__).resolve().parents[2] / "mt5"
SOURCES = sorted(MT5_DIR.glob("*.mq5")) + sorted(MT5_DIR.glob("*.mqh"))


def test_the_sources_are_where_the_tests_expect_them():
    """A moved folder must fail loudly, not silently pass every check below."""
    assert SOURCES, f"не найдено ни одного исходника MQL5 в {MT5_DIR}"


@pytest.mark.parametrize("src", SOURCES, ids=lambda p: p.name)
def test_socket_buffers_are_uchar(src: Path):
    """SocketSend/SocketRead are declared with uchar&[]; char[] will not convert."""
    text = src.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        assert "char " not in stripped.replace("uchar ", ""), (
            f"{src.name}:{lineno} объявляет буфер как char — "
            f"SocketSend/SocketRead принимают uchar&[]: {stripped}"
        )


@pytest.mark.parametrize("src", SOURCES, ids=lambda p: p.name)
def test_string_trim_is_not_returned_as_a_value(src: Path):
    """StringTrim* returns a count, not the trimmed string."""
    text = src.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        for fn in ("StringTrimRight", "StringTrimLeft"):
            assert not stripped.startswith(f"return {fn}("), (
                f"{src.name}:{lineno} возвращает результат {fn} — это число "
                f"снятых символов, а не строка; резать надо на месте, "
                f"возвращать саму переменную"
            )
