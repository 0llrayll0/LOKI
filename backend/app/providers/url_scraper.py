from __future__ import annotations

import re
import urllib.request
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlparse

from app.providers.base import Observation


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.paragraphs = []
        self._buf = []
        self.links = []
        self._current_tag = None
    def handle_starttag(self, tag, attrs):
        if tag == "title": self._in_title = True
        self._current_tag = tag
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v: self.links.append(v)
    def handle_endtag(self, tag):
        if tag == "title": self._in_title = False
        if tag == "p":
            text = " ".join("".join(self._buf).split())
            if text: self.paragraphs.append(text)
            self._buf = []
        if self._current_tag == tag: self._current_tag = None
    def handle_data(self, data):
        if self._in_title: self.title += data
        if self._current_tag == "p": self._buf.append(data)


class UrlScraperProvider:
    def __init__(self, name, url, timeout=10):
        self.name = name
        self.url = url
        self.timeout = timeout
    def _validate(self):
        parsed = urlparse(self.url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("url deve usar scheme http ou https")
        if not parsed.netloc:
            raise ValueError("url invalida: host ausente")
    def fetch(self):
        self._validate()
        req = urllib.request.Request(self.url, headers={"User-Agent": "loki-url-scraper/1"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except Exception as exc:
            raise RuntimeError(f"falha ao buscar url: {exc}") from exc
        html = raw.decode("utf-8", errors="replace")
        parser = _TextParser()
        try:
            parser.feed(html)
        except Exception:
            pass
        title = " ".join(parser.title.split()).strip()
        now = datetime.now()
        return [Observation(source=self.url, observed_at=now, payload={"title": title, "paragraphs": parser.paragraphs[:10], "links": parser.links[:20]})]
    @staticmethod
    def top_words(paragraphs, n=10):
        words = re.findall(r"\w{3,}", " ".join(paragraphs).lower())
        c = Counter(words)
        return [{"word": w, "count": cnt} for w, cnt in c.most_common(n)]
