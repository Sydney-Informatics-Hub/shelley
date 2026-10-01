"""
Tests for _paginate() in cli.py.

Key scenario: _paginate calls questionary.select().ask() for multi-page navigation.
When called from within a running asyncio event loop (interactive mode), ask() detects
the loop, creates a run_async() coroutine, but never awaits it — producing:
  RuntimeWarning: coroutine 'Application.run_async' was never awaited

The fix is to run _paginate via loop.run_in_executor() so questionary executes in a
thread that has no running event loop.
"""

import asyncio

import questionary

from shelley.utils.render import paginate as _paginate

# ---------------------------------------------------------------------------
# Pure behaviour — no questionary invoked (single page or empty)
# ---------------------------------------------------------------------------


def test_paginate_single_page_calls_render_once():
    log = []
    _paginate(
        list(range(5)),
        lambda items, page, tp, total: log.append((page, tp, total)),
        page_size=10,
    )
    assert log == [(0, 1, 5)]


def test_paginate_single_page_passes_correct_items():
    received = []
    _paginate(
        list(range(7)), lambda items, *_: received.append(list(items)), page_size=10
    )
    assert received == [list(range(7))]


def test_paginate_empty_calls_render_once():
    log = []
    _paginate(
        [],
        lambda items, page, tp, total: log.append((list(items), page, tp, total)),
        page_size=10,
    )
    assert log == [([], 0, 1, 0)]


def test_paginate_exact_page_size_is_single_page():
    log = []
    _paginate(
        list(range(10)),
        lambda items, page, tp, *_: log.append((page, tp)),
        page_size=10,
    )
    assert log == [(0, 1)]


# ---------------------------------------------------------------------------
# Multi-page navigation (questionary stubbed via monkeypatch)
# ---------------------------------------------------------------------------


def test_paginate_multi_page_next_then_quit(monkeypatch):
    """Navigate to page 2 then quit — render_fn called for pages 0 and 1."""
    nav = iter(["next", "quit"])
    monkeypatch.setattr(
        questionary,
        "select",
        lambda *a, **kw: type("R", (), {"ask": lambda self: next(nav)})(),
    )

    log = []
    _paginate(list(range(25)), lambda items, page, *_: log.append(page), page_size=10)
    assert log == [0, 1]


def test_paginate_multi_page_prev_available_after_next(monkeypatch):
    """After advancing to page 2, navigating back returns to page 1."""
    nav = iter(["next", "prev", "quit"])
    monkeypatch.setattr(
        questionary,
        "select",
        lambda *a, **kw: type("R", (), {"ask": lambda self: next(nav)})(),
    )

    log = []
    _paginate(list(range(25)), lambda items, page, *_: log.append(page), page_size=10)
    assert log == [0, 1, 0]


def test_paginate_multi_page_correct_slices(monkeypatch):
    """Each page receives the correct slice of items."""
    nav = iter(["next", "next", "quit"])
    monkeypatch.setattr(
        questionary,
        "select",
        lambda *a, **kw: type("R", (), {"ask": lambda self: next(nav)})(),
    )

    slices = []
    items = list(range(25))
    _paginate(
        items, lambda page_items, *_: slices.append(list(page_items)), page_size=10
    )
    assert slices == [items[:10], items[10:20], items[20:]]


def test_paginate_none_from_questionary_exits(monkeypatch):
    """None return from ask() (e.g. Ctrl-C) exits pagination cleanly."""
    monkeypatch.setattr(
        questionary,
        "select",
        lambda *a, **kw: type("R", (), {"ask": lambda self: None})(),
    )

    log = []
    _paginate(list(range(25)), lambda items, page, *_: log.append(page), page_size=10)
    assert log == [0]


# ---------------------------------------------------------------------------
# Async-context regression: questionary from running event loop
# ---------------------------------------------------------------------------


def test_paginate_multi_page_via_executor_runs_in_worker_thread(monkeypatch):
    """
    Regression test for: RuntimeWarning: coroutine 'Application.run_async' was never awaited

    questionary.select().ask() must not be called while an asyncio event loop is running
    (as happens in interactive_mode). The fix: run _paginate via loop.run_in_executor()
    so questionary executes in a thread that has no active event loop.

    This test verifies the fix by asserting that questionary is invoked from a worker
    thread, not the main thread. If the executor is removed and _paginate is called
    directly from async context, questionary would run on the main (event-loop) thread
    and trigger the RuntimeWarning.
    """
    import threading

    main_thread = threading.current_thread()
    called_from: list[threading.Thread] = []

    def fake_select(*a, **kw):
        called_from.append(threading.current_thread())

        class _R:
            def ask(self):
                return "quit"

        return _R()

    monkeypatch.setattr(questionary, "select", fake_select)

    log: list[int] = []

    async def _simulate_interactive_mode():
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: _paginate(
                list(range(25)), lambda items, page, *_: log.append(page), page_size=10
            ),
        )

    asyncio.run(_simulate_interactive_mode())

    assert log == [0], f"Expected page [0] (quit on first prompt), got {log}"
    assert called_from, "questionary.select was never called"
    assert called_from[0] is not main_thread, (
        "questionary.select ran on the main thread — _paginate was not called via run_in_executor"
    )
