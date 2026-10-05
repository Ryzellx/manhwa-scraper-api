"""Pydantic models for Manhwa Scraper API."""
from pydantic import BaseModel, Field
from typing import Optional


class MangaItem(BaseModel):
    id: str = Field(description="Manga slug, e.g. 'solo-leveling'")
    title: str
    cover: Optional[str] = None
    url: str
    latest_chapter: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    page: int
    has_next: bool
    results: list[MangaItem]


class MangaDetail(BaseModel):
    id: str
    title: str
    cover: Optional[str] = None
    url: str
    author: Optional[str] = None
    artist: Optional[str] = None
    status: Optional[str] = None
    genres: list[str] = []
    description: Optional[str] = None
    rating: Optional[str] = None


class ChapterItem(BaseModel):
    id: str = Field(description="Chapter slug, e.g. 'chapter-100'")
    manga_id: str
    title: str
    url: str
    date: Optional[str] = None


class ChaptersResponse(BaseModel):
    manga_id: str
    manga_title: str
    count: int
    chapters: list[ChapterItem]


class ChapterImages(BaseModel):
    chapter_id: str
    manga_id: str
    title: str
    url: str
    image_count: int
    images: list[str] = Field(description="Direct image URLs (use /api/v1/image?url= to proxy if hotlink-blocked)")
    prev_chapter: Optional[str] = None
    next_chapter: Optional[str] = None


class LatestResponse(BaseModel):
    page: int
    has_next: bool
    results: list[MangaItem]


class DomainInfo(BaseModel):
    configured: str
    current: str
    rotated: bool = Field(description="True if current differs from configured (auto-detected redirect)")


class DomainSet(BaseModel):
    domain: str = Field(description="New base domain, e.g. 'https://12.shinigami.asia'")


class HealthResponse(BaseModel):
    ok: bool = True
    site: str = "shinigami"
    domain: str
