"""A signal must still publish when its chart clip cannot be rendered.

`geometry` was computed inside the `if clip:` branch and read again in the
`else:` branch that sends the plain card. With no clip — no candles, no ffmpeg —
the else branch hit UnboundLocalError, the exception handler logged
"broadcast_error", and the signal was never published.

It hit precisely the instruments Yahoo has no candles for: SILV and RTS both
failed this way on 2026-10-29 while EURJPY, which did get a clip, went out
fine. Two of five pending signals, with nothing in the log naming the cause.
"""
import ast
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1] / "app" / "services" / "signal_pipeline.py"


def _broadcast_body() -> ast.AST:
    tree = ast.parse(PIPELINE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "process_and_broadcast":
            return node
    raise AssertionError("process_and_broadcast not found")


def test_geometry_is_bound_before_both_send_paths():
    """Assigned at a shallower level than every read of it.

    Compared by column offset rather than by text: the point is that no branch
    can reach a read without passing the assignment.
    """
    fn = _broadcast_body()
    assigns, reads = [], []
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and node.id == "geometry":
            (assigns if isinstance(node.ctx, ast.Store) else reads).append(node)

    assert assigns, "geometry is never assigned"
    assert reads, "geometry is never read — did the card stop showing the baseline?"

    outermost = min(a.col_offset for a in assigns)
    for r in reads:
        assert r.col_offset >= outermost, (
            f"geometry читается на строке {r.lineno} на уровне мельче присваивания "
            f"— значит, есть ветка, где оно не определено"
        )


def test_the_fallback_card_still_gets_the_baseline():
    """Hoisting must not turn into "pass None to the card and move on"."""
    src = PIPELINE.read_text(encoding="utf-8")
    assert src.count("geometry=geometry") == 2, (
        "и клип, и запасная карточка должны получать baseline"
    )


def test_a_failed_clip_does_not_abort_the_send():
    """The clip is optional; the message is not."""
    src = PIPELINE.read_text(encoding="utf-8")
    i = src.index("Clip render failed")
    # The fallback branch has to exist after the clip attempt, not instead of it.
    assert "broadcast_card" in src[i:], \
        "без клипа должна отправляться обычная карточка"
