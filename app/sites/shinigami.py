"""Shinigami adapter (WordPress Madara theme)."""
import re
from urllib.parse import quote_plus, urlparse
from bs4 import BeautifulSoup

from app.sites.base import BaseMangaAdapter
from app.models import MangaItem, MangaDetail, ChapterItem, ChapterImages


def _slug(url: str) -> str:
    return urlparse(url).path.strip("/").split("/")[-1]


def _img(tag) -> str | None:
    if not tag:
        return None
    return tag.get("data-src") or tag.get("data-lazy-src") or tag.get("src")


class ShinigamiAdapter(BaseMangaAdapter):
    name = "shinigami"

    def __init__(self, base: str):
        self.base = base.rstrip("/")

    # ---- URL builders ----
    def search_url(self, query: str, page: int = 1) -> str:
        u = f"{self.base}/?s={quote_plus(query)}&post_type=wp-manga"
        return f"{u}&page={page}" if page > 1 else u

    def latest_url(self, page: int = 1) -> str:
        u = f"{self.base}/manga/?m_orderby=latest"
        return f"{u}&page={page}" if page > 1 else u

    def popular_url(self, page: int = 1) -> str:
        u = f"{self.base}/manga/?m_orderby=views"
        return f"{u}&page={page}" if page > 1 else u

    def manga_url(self, manga_id: str) -> str:
        if manga_id.startswith("http"):
            return manga_id
        return f"{self.base}/manga/{manga_id.strip('/')}/"

    def chapter_url(self, chapter_id: str, manga_id: str = "") -> str:
        if chapter_id.startswith("http"):
            return chapter_id
        if manga_id:
            return f"{self.base}/manga/{manga_id.strip('/')}/{chapter_id.strip('/')}/"
        return f"{self.base}/{chapter_id.strip('/')}/"

    # ---- parsers ----
    def _parse_list(self, soup: BeautifulSoup) -> tuple[list[MangaItem], bool]:
        items: list[MangaItem] = []
        for div in soup.select("div.page-item-detail.manga"):
            a = div.select_one("h3.h5 a, h3 a, div.post-title a, a[title]")
            if not a:
                a = div.select_one("a")
            if not a or not a.get("href"):
                continue
            href = a["href"]
            title = (a.get("title") or a.get_text(strip=True)).strip()
            cover = _img(div.select_one("img"))
            # latest chapter label if present
            latest = None
            lc = div.select_one("span.chapter a, div.list-chapter a")
            if lc:
                latest = lc.get_text(strip=True)
            items.append(MangaItem(id=_slug(href), title=title, cover=cover,
                                   url=href, latest_chapter=latest))
        has_next = bool(soup.select_one("a.nextpostslink, a.next.page-numbers"))
        return items, has_next

    def parse_search(self, soup: BeautifulSoup, query: str, page: int) -> list[MangaItem]:
        items, _ = self._parse_list(soup)
        # Madara search results sometimes use different markup
        if not items:
            for div in soup.select("div.c-tabs-item__content, div.search-wrap div.tab-thumb"):
                a = div.select_one("a[title]") or div.select_one("a")
                if not a or not a.get("href"):
                    continue
                href = a["href"]
                if "/manga/" not in href:
                    continue
                title = (a.get("title") or a.get_text(strip=True)).strip()
                items.append(MangaItem(id=_slug(href), title=title,
                                       cover=_img(div.select_one("img")), url=href))
        return items

    def parse_latest(self, soup: BeautifulSoup, page: int) -> tuple[list[MangaItem], bool]:
        return self._parse_list(soup)

    def _summary_field(self, soup: BeautifulSoup, label: str) -> str | None:
        for row in soup.select("div.post-content_item, div.summary-content"):
            heading = row.select_one("div.summary-heading h5, h5")
            if heading and label.lower() in heading.get_text(strip=True).lower():
                val = row.select_one("div.summary-content, div.summary-content a")
                if val:
                    return val.get_text(strip=True)
        return None

    def parse_manga_detail(self, soup: BeautifulSoup, manga_id: str, url: str) -> MangaDetail:
        title_el = soup.select_one("div.post-title h1, h1.entry-title")
        title = title_el.get_text(strip=True) if title_el else manga_id
        cover = _img(soup.select_one("div.summary_image img, div.tab-summary img"))
        desc_el = soup.select_one("div.description-summary div.summary__content, div.summary__content")
        description = desc_el.get_text(" ", strip=True) if desc_el else None
        genres = [a.get_text(strip=True) for a in soup.select("div.genres-content a")]
        author = None
        artist = None
        for row in soup.select("div.post-content_item"):
            h = row.select_one("h5")
            if not h:
                continue
            label = h.get_text(strip=True).lower()
            val = ", ".join(a.get_text(strip=True) for a in row.select("a")) or \
                row.select_one("div.summary-content").get_text(strip=True) if row.select_one("div.summary-content") else None
            if "author" in label:
                author = val
            elif "artist" in label:
                artist = val
        status = self._summary_field(soup, "status")
        rating = None
        r = soup.select_one("span.score, div.post-rating span.score")
        if r:
            rating = r.get_text(strip=True)
        return MangaDetail(id=_slug(url) or manga_id, title=title, cover=cover, url=url,
                           author=author, artist=artist, status=status, genres=genres,
                           description=description, rating=rating)

    def parse_chapters(self, soup: BeautifulSoup, manga_id: str) -> tuple[str, list[ChapterItem]]:
        title_el = soup.select_one("div.post-title h1")
        manga_title = title_el.get_text(strip=True) if title_el else manga_id
        chapters: list[ChapterItem] = []
        for li in soup.select("li.wp-manga-chapter"):
            a = li.select_one("a")
            if not a or not a.get("href"):
                continue
            href = a["href"]
            ch_slug = _slug(href)
            ch_title = a.get_text(" ", strip=True)
            date_el = li.select_one("span.chapter-release-date")
            chapters.append(ChapterItem(id=ch_slug, manga_id=manga_id, title=ch_title,
                                        url=href, date=date_el.get_text(strip=True) if date_el else None))
        return manga_title, chapters

    def parse_chapter_images(self, soup: BeautifulSoup, chapter_id: str,
                             manga_id: str, url: str) -> ChapterImages:
        title_el = soup.select_one("h1#chapter-heading, div.post-title h1, h1.entry-title")
        title = title_el.get_text(strip=True) if title_el else chapter_id
        images: list[str] = []
        for img in soup.select("div.page-break img, div.reading-content img"):
            src = _img(img)
            if src and src not in images and not src.startswith("data:"):
                images.append(src.strip())
        # prev/next navigation
        prev_id = next_id = None
        prev_a = soup.select_one("a.prev_page, div.prev-chap a")
        next_a = soup.select_one("a.next_page, div.next-chap a")
        if prev_a and prev_a.get("href"):
            prev_id = _slug(prev_a["href"])
        if next_a and next_a.get("href"):
            next_id = _slug(next_a["href"])
        # manga slug from URL path: /manga/{manga}/{chapter}/
        parts = urlparse(url).path.strip("/").split("/")
        mid = parts[1] if len(parts) >= 3 and parts[0] == "manga" else manga_id
        return ChapterImages(chapter_id=_slug(url) or chapter_id, manga_id=mid, title=title,
                             url=url, image_count=len(images), images=images,
                             prev_chapter=prev_id, next_chapter=next_id)
