"""Begrenzte HTTPS-Aufrufe ohne Redirects oder fremde Fehlertexte."""

import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


class CloudError(ValueError):
    def __init__(self, status=0, expired_grant=False):
        self.status = status
        self.expired_grant = expired_grant
        super().__init__(
            f"Anbieter hat die Anfrage abgewiesen (HTTP {status}). Zugang, Berechtigungen oder Kontingent prüfen."
            if status
            else "Anbieter nicht erreichbar oder Antwort ungültig. Verbindung prüfen."
        )


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


async def request_json(
    method,
    url,
    *,
    token=None,
    data=None,
    form=False,
    timeout=8,
    headers=None,
    max_bytes=1_000_000,
):
    extra_headers = dict(headers or {})

    def send():
        headers = {"Accept": "application/json", **extra_headers}
        if token:
            headers["Authorization"] = "Bearer " + token
        payload = None
        if data is not None:
            payload = urlencode(data).encode() if form else json.dumps(data).encode()
            headers["Content-Type"] = (
                "application/x-www-form-urlencoded" if form else "application/json"
            )
        try:
            with build_opener(NoRedirect()).open(
                Request(url, data=payload, headers=headers, method=method),
                timeout=timeout,
            ) as response:
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise CloudError()
                value = json.loads(body) if body else {}
                if not isinstance(value, dict):
                    raise CloudError()
                return value
        except HTTPError as error:
            # Nur dieser bekannte OAuth-Fehler beeinflusst den Ablauf. Kein Body im Log.
            expired = False
            try:
                expired = json.loads(error.read(8192)).get("error") == "invalid_grant"
            except (ValueError, AttributeError, UnicodeError):
                pass
            raise CloudError(error.code, expired) from None
        except (URLError, OSError, ValueError, UnicodeError) as error:
            if isinstance(error, CloudError):
                raise
            raise CloudError() from None

    return await asyncio.to_thread(send)
