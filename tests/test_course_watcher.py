import pytest

from cogs.course_watcher import CourseWatcher


class _FakeResponse:
    def __init__(self, status, text, url="https://example.com/course"):
        self.status = status
        self._text = text
        self.url = url

    async def text(self):
        return self._text


class _FakeRequestCtx:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.calls = 0

    def request(self, method, url, **kwargs):
        self.calls += 1
        return _FakeRequestCtx(next(self._responses))


@pytest.mark.asyncio
async def test_request_text_with_retry_succeeds_after_retry(monkeypatch):
    watcher = object.__new__(CourseWatcher)

    sleep_calls = []

    async def _fake_sleep_backoff(attempt):
        sleep_calls.append(attempt)

    monkeypatch.setattr(watcher, "_sleep_backoff", _fake_sleep_backoff)

    session = _FakeSession(
        [
            _FakeResponse(429, "rate limited"),
            _FakeResponse(200, "<html>ok</html>", "https://example.com/final"),
        ]
    )

    result = await CourseWatcher._request_text_with_retry(
        watcher,
        session,
        "GET",
        "https://example.com/course",
        max_attempts=3,
    )

    assert result["ok"] is True
    assert result["status"] == 200
    assert result["text"] == "<html>ok</html>"
    assert session.calls == 2
    assert sleep_calls == [1]


@pytest.mark.asyncio
async def test_request_text_with_retry_flags_blocked_for_cloudflare(monkeypatch):
    watcher = object.__new__(CourseWatcher)

    async def _fake_sleep_backoff(_attempt):
        return None

    monkeypatch.setattr(watcher, "_sleep_backoff", _fake_sleep_backoff)

    session = _FakeSession(
        [_FakeResponse(403, "<html>Cloudflare error 1015</html>")]
    )

    result = await CourseWatcher._request_text_with_retry(
        watcher,
        session,
        "GET",
        "https://example.com/course",
        max_attempts=1,
    )

    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["reason"] == "cloudflare-bloqueo"
