"""Manhwa Scraper REST API — Shinigami (Madara)."""
import os

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.models import (SearchResponse, MangaDetail, ChaptersResponse, ChapterImages,
                        LatestResponse, DomainInfo, DomainSet, HealthResponse)
from app.fetcher import Fetcher, FetchError, DomainManager
from app.sites.shinigami import ShinigamiAdapter

DEFAULT_DOMAIN = os.environ.get("SHINIGAMI_DOMAIN", "https://11.shinigami.asia")

domains = DomainManager(DEFAULT_DOMAIN)
fetcher = Fetcher(domains)
adapter = ShinigamiAdapter(domains.base())

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app = FastAPI(title="Manhwa Scraper API",
              description="REST API scraper manhwa — Shinigami (auto domain rotation)",
              version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _adapter() -> ShinigamiAdapter:
    adapter.base = domains.base()
    return adapter


def _err(e: FetchError):
    if e.kind == "BLOCKED_BY_CLOUDFLARE":
        return JSONResponse({"error": "upstream_blocked",
                             "detail": "Target diblokir Cloudflare dari IP server ini."}, 502)
    if e.kind == "NOT_FOUND":
        return JSONResponse({"error": "not_found", "detail": e.detail}, 404)
    if e.kind == "NETWORK_ERROR":
        return JSONResponse({"error": "network_error", "detail": e.detail}, 502)
    return JSONResponse({"error": "scrape_failed", "detail": e.kind}, 502)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(site="shinigami", domain=domains.base())


@app.get("/api/v1/domain", response_model=DomainInfo)
def get_domain():
    return DomainInfo(**domains.info())


@app.post("/api/v1/domain", response_model=DomainInfo)
def set_domain(body: DomainSet):
    try:
        domains.set(body.domain)
    except ValueError as e:
        return JSONResponse({"error": "invalid_domain", "detail": str(e)}, 400)
    return DomainInfo(**domains.info())


@app.get("/api/v1/search", response_model=SearchResponse)
@limiter.limit("30/minute")
def search(request: Request, q: str = Query(..., min_length=2), page: int = Query(1, ge=1)):
    a = _adapter()
    try:
        _, soup = fetcher.get(a.search_url(q, page))
        items = a.parse_search(soup, q, page)
        has_next = bool(soup.select_one("a.nextpostslink, a.next.page-numbers"))
        return SearchResponse(query=q, page=page, has_next=has_next, results=items)
    except FetchError as e:
        return _err(e)


@app.get("/api/v1/latest", response_model=LatestResponse)
@limiter.limit("15/minute")
def latest(request: Request, page: int = Query(1, ge=1)):
    a = _adapter()
    try:
        _, soup = fetcher.get(a.latest_url(page))
        items, has_next = a.parse_latest(soup, page)
        return LatestResponse(page=page, has_next=has_next, results=items)
    except FetchError as e:
        return _err(e)


@app.get("/api/v1/popular", response_model=LatestResponse)
@limiter.limit("15/minute")
def popular(request: Request, page: int = Query(1, ge=1)):
    a = _adapter()
    try:
        _, soup = fetcher.get(a.popular_url(page))
        items, has_next = a.parse_latest(soup, page)
        return LatestResponse(page=page, has_next=has_next, results=items)
    except FetchError as e:
        return _err(e)


@app.get("/api/v1/manga", response_model=MangaDetail)
@limiter.limit("30/minute")
def manga(request: Request, id: str = Query(..., description="Manga slug atau URL penuh")):
    a = _adapter()
    try:
        final_url, soup = fetcher.get(a.manga_url(id))
        return a.parse_manga_detail(soup, id, final_url)
    except FetchError as e:
        return _err(e)


@app.get("/api/v1/chapters", response_model=ChaptersResponse)
@limiter.limit("20/minute")
def chapters(request: Request, manga_id: str = Query(..., description="Manga slug")):
    a = _adapter()
    try:
        _, soup = fetcher.get(a.manga_url(manga_id))
        title, chs = a.parse_chapters(soup, manga_id)
        return ChaptersResponse(manga_id=manga_id, manga_title=title,
                                count=len(chs), chapters=chs)
    except FetchError as e:
        return _err(e)


@app.get("/api/v1/chapter", response_model=ChapterImages)
@limiter.limit("20/minute")
def chapter(request: Request, id: str = Query(..., description="Chapter slug atau URL penuh"),
            manga_id: str = Query("", description="Manga slug (opsional, membantu URL)")):
    a = _adapter()
    try:
        final_url, soup = fetcher.get(a.chapter_url(id, manga_id))
        return a.parse_chapter_images(soup, id, manga_id, final_url)
    except FetchError as e:
        return _err(e)


@app.get("/api/v1/image")
@limiter.limit("60/minute")
def image_proxy(request: Request, url: str = Query(..., description="URL gambar chapter")):
    """Proxy gambar chapter (atasi hotlink protection via Referer)."""
    try:
        data, ctype = fetcher.get_image(url)
        return Response(content=data, media_type=ctype,
                        headers={"Cache-Control": "public, max-age=86400"})
    except FetchError as e:
        return _err(e)


@app.post("/api/v1/cache/clear")
def cache_clear():
    fetcher.clear_cache()
    return {"ok": True}
