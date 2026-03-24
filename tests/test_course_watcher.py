import pytest

from cogs.course_watcher import BROWSER_HEADERS, CourseWatcher


class _FakeResponse:
    def __init__(self, status, text, url="https://example.com/course", headers=None):
        self.status = status
        self._text = text
        self.url = url
        self.headers = headers or {}

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
        self.last_kwargs = {}

    def request(self, method, url, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
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


@pytest.mark.asyncio
async def test_request_includes_browser_headers(monkeypatch):
    """Las peticiones deben incluir cabeceras de navegador para evitar bloqueos WAF/Cloudflare."""
    watcher = object.__new__(CourseWatcher)

    async def _fake_sleep_backoff(_attempt):
        return None

    monkeypatch.setattr(watcher, "_sleep_backoff", _fake_sleep_backoff)
    monkeypatch.setenv("CVIRTUAL_COOKIE", "")

    session = _FakeSession(
        [_FakeResponse(200, "<html>ok</html>", "https://example.com/ok")]
    )

    await CourseWatcher._request_text_with_retry(
        watcher,
        session,
        "GET",
        "https://example.com/course",
        max_attempts=1,
    )

    sent_headers = session.last_kwargs.get("headers", {})
    assert "User-Agent" in sent_headers
    assert "Mozilla" in sent_headers["User-Agent"]
    assert "Accept" in sent_headers


def test_cookie_request_kwargs_always_includes_browser_headers(monkeypatch):
    """_cookie_request_kwargs debe incluir siempre las cabeceras de navegador."""
    watcher = object.__new__(CourseWatcher)
    monkeypatch.setenv("CVIRTUAL_COOKIE", "")

    kwargs = CourseWatcher._cookie_request_kwargs(watcher, use_manual_cookie=False)

    assert "headers" in kwargs
    headers = kwargs["headers"]
    for key in BROWSER_HEADERS:
        assert key in headers, f"Cabecera esperada '{key}' no encontrada"


def test_cookie_request_kwargs_merges_cookie_with_browser_headers(monkeypatch):
    """Cuando se usa CVIRTUAL_COOKIE, debe combinarse con las cabeceras de navegador."""
    watcher = object.__new__(CourseWatcher)
    monkeypatch.setenv("CVIRTUAL_COOKIE", "abc123session")

    kwargs = CourseWatcher._cookie_request_kwargs(watcher, use_manual_cookie=True)

    headers = kwargs["headers"]
    assert "Cookie" in headers
    assert "abc123session" in headers["Cookie"]
    assert "User-Agent" in headers


def test_parse_retry_after_numeric():
    """_parse_retry_after debe devolver segundos numéricos del encabezado."""
    watcher = object.__new__(CourseWatcher)
    result = CourseWatcher._parse_retry_after(watcher, {"Retry-After": "30"})
    assert result == 30.0


def test_parse_retry_after_missing():
    """_parse_retry_after devuelve None si no hay encabezado."""
    watcher = object.__new__(CourseWatcher)
    assert CourseWatcher._parse_retry_after(watcher, {}) is None
    assert CourseWatcher._parse_retry_after(watcher, None) is None


def test_parse_retry_after_capped_at_max():
    """_parse_retry_after no debe superar 120 segundos."""
    watcher = object.__new__(CourseWatcher)
    result = CourseWatcher._parse_retry_after(watcher, {"Retry-After": "9999"})
    assert result == 120.0


@pytest.mark.asyncio
async def test_retry_after_header_used_instead_of_backoff(monkeypatch):
    """Si el servidor devuelve Retry-After, se usa ese valor en vez del backoff exponencial."""
    watcher = object.__new__(CourseWatcher)

    backoff_calls = []
    sleep_calls = []

    async def _fake_sleep_backoff(attempt):
        backoff_calls.append(attempt)

    async def _fake_asyncio_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(watcher, "_sleep_backoff", _fake_sleep_backoff)
    monkeypatch.setattr("cogs.course_watcher.asyncio.sleep", _fake_asyncio_sleep)

    session = _FakeSession(
        [
            _FakeResponse(429, "too many requests", headers={"Retry-After": "45"}),
            _FakeResponse(200, "<html>ok</html>", "https://example.com/ok"),
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
    # El backoff exponencial NO debe haberse llamado para la espera por Retry-After.
    assert backoff_calls == []
    # asyncio.sleep sí debe haberse llamado con el valor del encabezado.
    assert 45.0 in sleep_calls

