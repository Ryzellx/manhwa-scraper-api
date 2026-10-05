import * as cheerio from "cheerio";

const slug = (url) => { try { return new URL(url).pathname.replace(/\/$/, "").split("/").pop(); } catch { return url; }; };
const img = ($el) => { if (!$el || !$el.length) return null; return $el.attr("data-src") || $el.attr("data-lazy-src") || $el.attr("src"); };

export class ShinigamiAdapter {
  constructor(base) { this.base = base.replace(/\/$/, ""); }
  searchUrl(q, page = 1) { const u = `${this.base}/?s=${encodeURIComponent(q)}&post_type=wp-manga`; return page > 1 ? `${u}&page=${page}` : u; }
  latestUrl(page = 1) { const u = `${this.base}/manga/?m_orderby=latest`; return page > 1 ? `${u}&page=${page}` : u; }
  popularUrl(page = 1) { const u = `${this.base}/manga/?m_orderby=views`; return page > 1 ? `${u}&page=${page}` : u; }
  mangaUrl(id) { return id.startsWith("http") ? id : `${this.base}/manga/${id.replace(/\/$/, "")}/`; }
  chapterUrl(id, mangaId = "") {
    if (id.startsWith("http")) return id;
    return mangaId ? `${this.base}/manga/${mangaId.replace(/\/$/, "")}/${id.replace(/\/$/, "")}/`
                   : `${this.base}/${id.replace(/\/$/, "")}/`;
  }

  _parseList($) {
    const items = [];
    $("div.page-item-detail.manga").each((_, el) => {
      const div = $(el);
      let a = div.find("h3.h5 a, h3 a, div.post-title a, a[title]").first();
      if (!a.length) a = div.find("a").first();
      const href = a.attr("href");
      if (!href) return;
      const title = (a.attr("title") || a.text()).trim();
      const lc = div.find("span.chapter a, div.list-chapter a").first();
      items.push({ id: slug(href), title, cover: img(div.find("img").first()) || null,
                   url: href, latest_chapter: lc.length ? lc.text().trim() : null });
    });
    return { items, hasNext: $("a.nextpostslink, a.next.page-numbers").length > 0 };
  }
  parseSearch($) {
    let { items } = this._parseList($);
    if (!items.length) {
      $("div.c-tabs-item__content, div.search-wrap div.tab-thumb").each((_, el) => {
        const div = $(el);
        const a = div.find("a[title]").first().length ? div.find("a[title]").first() : div.find("a").first();
        const href = a.attr("href");
        if (!href || !href.includes("/manga/")) return;
        items.push({ id: slug(href), title: (a.attr("title") || a.text()).trim(),
                     cover: img(div.find("img").first()) || null, url: href, latest_chapter: null });
      });
    }
    return items;
  }
  parseLatest($) { return this._parseList($); }

  _summaryField($, label) {
    let out = null;
    $("div.post-content_item, div.summary-content").each((_, el) => {
      const h = $(el).find("div.summary-heading h5, h5").first();
      if (h.length && h.text().toLowerCase().includes(label.toLowerCase())) {
        const v = $(el).find("div.summary-content, div.summary-content a").first();
        if (v.length) out = v.text().trim();
      }
    });
    return out;
  }
  parseMangaDetail($, mangaId, url) {
    const title = $("div.post-title h1, h1.entry-title").first().text().trim() || mangaId;
    const desc = $("div.description-summary div.summary__content, div.summary__content").first().text().replace(/\s+/g, " ").trim() || null;
    const genres = $("div.genres-content a").map((_, a) => $(a).text().trim()).get();
    let author = null, artist = null;
    $("div.post-content_item").each((_, el) => {
      const h = $(el).find("h5").first();
      if (!h.length) return;
      const label = h.text().toLowerCase();
      const links = $(el).find("a").map((_, a) => $(a).text().trim()).get().join(", ");
      const val = links || $(el).find("div.summary-content").first().text().trim() || null;
      if (label.includes("author")) author = val;
      else if (label.includes("artist")) artist = val;
    });
    const rating = $("span.score, div.post-rating span.score").first().text().trim() || null;
    return { id: slug(url) || mangaId, title, cover: img($("div.summary_image img, div.tab-summary img").first()) || null,
             url, author, artist, status: this._summaryField($, "status"), genres,
             description: desc, rating };
  }
  parseChapters($, mangaId) {
    const mangaTitle = $("div.post-title h1").first().text().trim() || mangaId;
    const chapters = [];
    $("li.wp-manga-chapter").each((_, el) => {
      const a = $(el).find("a").first();
      const href = a.attr("href");
      if (!href) return;
      const date = $(el).find("span.chapter-release-date").first().text().trim() || null;
      chapters.push({ id: slug(href), manga_id: mangaId, title: a.text().replace(/\s+/g, " ").trim(), url: href, date });
    });
    return { mangaTitle, chapters };
  }
  parseChapterImages($, chapterId, mangaId, url) {
    const title = $("h1#chapter-heading, div.post-title h1, h1.entry-title").first().text().trim() || chapterId;
    const seen = new Set(), images = [];
    $("div.page-break img, div.reading-content img").each((_, el) => {
      const src = (img($(el)) || "").trim();
      if (src && !src.startsWith("data:") && !seen.has(src)) { seen.add(src); images.push(src); }
    });
    const prevA = $("a.prev_page, div.prev-chap a").first();
    const nextA = $("a.next_page, div.next-chap a").first();
    let mid = mangaId;
    try { const p = new URL(url).pathname.replace(/\/$/, "").split("/"); if (p[1] === "manga" && p.length >= 4) mid = p[2]; } catch {}
    return { chapter_id: slug(url) || chapterId, manga_id: mid, title, url,
             image_count: images.length, images,
             prev_chapter: prevA.length ? slug(prevA.attr("href")) : null,
             next_chapter: nextA.length ? slug(nextA.attr("href")) : null };
  }
}

export const load = (html) => cheerio.load(html);
