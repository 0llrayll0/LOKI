from app.providers.url_scraper import UrlScraperProvider


def test_validate_scheme():
    p = UrlScraperProvider(name="x", url="ftp://example.com")
    try:
        p.fetch()
    except (ValueError, RuntimeError):
        pass
    else:
        raise AssertionError("expected error")


def test_top_words():
    rows = UrlScraperProvider.top_words(["hello hello world"], 2)
    assert rows[0]["word"] == "hello"
    assert rows[0]["count"] == 2
