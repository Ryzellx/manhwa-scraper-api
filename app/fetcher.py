"""HTTP fetcher with domain rotation, caching, and politeness delays.

Domain rotation: shinigami.asia rotates its numbered subdomain
(11.shinigami.asia -> 12.shinigami.asia -> ...). The old domain
HTTP-redirects to the new one. This fetcher follows redirects and,
when the final host is still under the same parent domain, promotes
it to the new base domain automatically and persists it to disk.
"""
import os

# sanitize no_proxy (IPv6 bracket entries crash urllib3/httpx)
os.environ["no_proxy"] = os.environ["NO_PROXY"] = "localhost,127.0.0.1"

import re
import time
import json
import threading
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

CACHE_TTL = 600          # 10 minutes
MIN_DELAY = 1.0          # politeness delay per domain
STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          ".domain_state.json")


def _parent_domain(host: str) -> str:
    """Extract parent domain: 11.shinigami.asia -> shinigami.asia"""
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


class DomainManager:
    """Tracks the live domain; auto-rotates on redirect."""

    def __init__(self, initial: str, state_file: str = STATE_FILE,
                 parent: str = "shinigami.asia"):
        self.configured = initial.rstrip("/")
        self.parent = parent
        self.state_file = state_file
        self._lock = threading.Lock()
        self.current = self.configured
        self.rotated = False
        self._load()

    def _load(self):
        try:
            with open(self.state_file) as f:
                data = json.load(f)
            saved = data.get("current", "")
            if saved and _parent_domain(urlparse(saved).hostname or "") == self.parent:
                self.current = saved.rstrip("/")
                self.rotated = self.current != self.configured
        except Exception:
            pass

    def _save(self):
        try:
            with open(self.state_file, "w") as f:
                json.dump({"current": self.current}, f)
        except Exception:
            pass

    def base(self) -> str:
        with self._lock:
            return self.current

    def set(self, domain: str):
        domain = domain.rstrip("/")
        host = urlparse(domain).hostname or ""
        if _parent_domain(host) != self.parent:
            raise ValueError(f"domain must be under {self.parent}")
        with self._lock:
            self.current = domain
            self.rotated = self.current != self.configured
            self._save()

    def observe(self, final_url: str) -> bool:
        """Check a response's final URL; rotate if host changed. Returns True if rotated."""
        host = urlparse(final_url).hostname or ""
        if not host or _parent_domain(host) != self.parent:
            return False
        new_base = f"https://{host}"
        with self._lock:
            if new_base != self.current:
                self.current = new_base
                self.rotated = self.current != self.configured
                self._save()
                return True
        return False

    def info(self) -> dict:
        with self._lock:
            return {"configured": self.configured, "current": self.current,
                    "rotated": self.rotated}


class FetchError(Exception):
    def __init__(self, kind: str, detail: str = ""):
        self.kind = kind
        self.detail = detail
        super().__init__(f"{kind}: {detail}")


class Fetcher:
    def __init__(self, domains: DomainManager):
        self.domains = domains
        self._cache: dict[str, tuple[float, str, str]] = {}  # url -> (ts, final_url, html)
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def _polite(self, host: str):
        with self._lock:
            last = self._last.get(host, 0)
            wait = MIN_DELAY - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        with self._lock:
            self._last[host] = time.time()

    def get(self, url: str) -> tuple[str, BeautifulSoup]:
        """Returns (final_url, soup). Follows redirects; rotates domain if needed."""
        now = time.time()
        with self._lock:
            hit = self._cache.get(url)
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1], BeautifulSoup(hit[2], "lxml")

        host = urlparse(url).hostname or ""
        self._polite(host)

        headers = {"User-Agent": UA, "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
                   "Referer": self.domains.base() + "/"}
        try:
            with httpx.Client(timeout=25, follow_redirects=True, headers=headers) as c:
                r = c.get(url)
        except httpx.RequestError as e:
            raise FetchError("NETWORK_ERROR", str(e)[:200])

        final_url = str(r.url)
        rotated = self.domains.observe(final_url)

        if r.status_code == 403:
            txt = r.text[:500].lower()
            if "cloudflare" in txt or "just a moment" in txt or "attention required" in txt:
                raise FetchError("BLOCKED_BY_CLOUDFLARE",
                                 "target is behind Cloudflare and blocks datacenter IPs")
            raise FetchError("HTTP_403_FORBIDDEN", f"final_url={final_url}")
        if r.status_code == 404:
            raise FetchError("NOT_FOUND", url)
        if r.status_code >= 400:
            raise FetchError(f"HTTP_{r.status_code}", f"final_url={final_url}")

        html = r.text
        with self._lock:
            self._cache[url] = (now, final_url, html)
        return final_url, BeautifulSoup(html, "lxml")

    def get_image(self, url: str) -> tuple[bytes, str]:
        """Fetch an image with proper Referer (for hotlink protection)."""
        headers = {"User-Agent": UA, "Referer": self.domains.base() + "/"}
        try:
            with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as c:
                r = c.get(url)
        except httpx.RequestError as e:
            raise FetchError("NETWORK_ERROR", str(e)[:200])
        if r.status_code >= 400:
            raise FetchError(f"HTTP_{r.status_code}", url)
        ctype = r.headers.get("content-type", "image/jpeg")
        return r.content, ctype

    def clear_cache(self):
        with self._lock:
            self._cache.clear()
