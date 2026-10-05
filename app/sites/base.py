"""Base adapter interface for manga sites."""
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup
from app.models import MangaItem, MangaDetail, ChapterItem, ChapterImages


class BaseMangaAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def search_url(self, query: str, page: int = 1) -> str: ...

    @abstractmethod
    def latest_url(self, page: int = 1) -> str: ...

    @abstractmethod
    def popular_url(self, page: int = 1) -> str: ...

    @abstractmethod
    def manga_url(self, manga_id: str) -> str: ...

    @abstractmethod
    def chapter_url(self, chapter_id: str, manga_id: str = "") -> str: ...

    @abstractmethod
    def parse_search(self, soup: BeautifulSoup, query: str, page: int) -> list[MangaItem]: ...

    @abstractmethod
    def parse_latest(self, soup: BeautifulSoup, page: int) -> tuple[list[MangaItem], bool]: ...

    @abstractmethod
    def parse_manga_detail(self, soup: BeautifulSoup, manga_id: str, url: str) -> MangaDetail: ...

    @abstractmethod
    def parse_chapters(self, soup: BeautifulSoup, manga_id: str) -> tuple[str, list[ChapterItem]]: ...

    @abstractmethod
    def parse_chapter_images(self, soup: BeautifulSoup, chapter_id: str, manga_id: str, url: str) -> ChapterImages: ...
