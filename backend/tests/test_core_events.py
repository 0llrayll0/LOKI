from app.core.events import EventBus


def test_multiple_handlers_and_off() -> None:
    bus = EventBus()
    calls = []

    def h1(p):
        calls.append(("h1", p))
        return 1

    def h2(p):
        calls.append(("h2", p))
        return 2

    bus.on("e", h1)
    bus.on("e", h2)
    res = bus.emit("e", 42)
    assert res == [1, 2]
    bus.off("e", h1)
    res = bus.emit("e", 7)
    assert res == [2]
    assert calls == [("h1", 42), ("h2", 42), ("h2", 7)]


def test_exceptions_isolated() -> None:
    bus = EventBus()
    seen = []

    def bad(p):
        raise ValueError("boom")

    def good(p):
        seen.append(p)
        return "ok"

    bus.on("e", bad)
    bus.on("e", good)
    res = bus.emit("e", 5)
    assert seen == [5]
    assert len(res) == 2
    assert isinstance(res[0], ValueError)
    assert res[1] == "ok"