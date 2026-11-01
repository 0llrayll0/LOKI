from app.core.providers import DuplicateProviderError, ProviderRegistry


def test_register_get_list_unregister() -> None:
    r = ProviderRegistry()
    r.register("p", object())
    assert "p" in r
    assert r.get("p") is not None
    assert r.list_names() == ["p"]
    r.unregister("p")
    assert "p" not in r


def test_duplicate_raises() -> None:
    r = ProviderRegistry()
    r.register("p", object())
    try:
        r.register("p", object())
    except DuplicateProviderError:
        pass
    else:
        raise AssertionError("expected duplicate error")


def test_get_missing_raises_keyerror() -> None:
    r = ProviderRegistry()
    try:
        r.get("x")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError")