import express from "express";
import rateLimit from "express-rate-limit";
import { DomainManager, Fetcher, FetchError } from "./fetcher.js";
import { ShinigamiAdapter, load } from "./adapter.js";

const DEFAULT_DOMAIN = process.env.SHINIGAMI_DOMAIN || "https://11.shinigami.asia";
const domains = new DomainManager(DEFAULT_DOMAIN);
const fetcher = new Fetcher(domains);
const adapter = () => { const a = new ShinigamiAdapter(domains.base()); return a; };

export function createApp() {
  const app = express();
  app.use(express.json());
  app.set("trust proxy", 1);

  const gl = rateLimit({ windowMs: 60_000, max: 60, standardHeaders: true, legacyHeaders: false,
    handler: (_, res) => res.status(429).json({ error: "rate_limited", detail: "Too many requests, slow down." }) });
  app.use(gl);
  const rl = (max) => rateLimit({ windowMs: 60_000, max, standardHeaders: true, legacyHeaders: false,
    handler: (_, res) => res.status(429).json({ error: "rate_limited", detail: "Too many requests, slow down." }) });

  const err = (e, res) => {
    if (!(e instanceof FetchError)) return res.status(500).json({ error: "internal", detail: String(e).slice(0, 200) });
    if (e.kind === "BLOCKED_BY_CLOUDFLARE") return res.status(502).json({ error: "upstream_blocked", detail: "Target diblokir Cloudflare dari IP server ini. Pakai proxy/IP residensial." });
    if (e.kind === "NOT_FOUND") return res.status(404).json({ error: "not_found", detail: e.detail });
    if (e.kind === "NETWORK_ERROR") return res.status(502).json({ error: "network_error", detail: e.detail });
    return res.status(502).json({ error: "scrape_failed", detail: e.kind });
  };

  app.get("/health", (_, res) => res.json({ ok: true, site: "shinigami", domain: domains.base() }));
  app.get("/api/v1/domain", (_, res) => res.json(domains.info()));
  app.post("/api/v1/domain", (req, res) => {
    try { domains.set(req.body.domain); res.json(domains.info()); }
    catch (e) { res.status(400).json({ error: "invalid_domain", detail: e.message }); }
  });

  app.get("/api/v1/search", rl(30), async (req, res) => {
    const q = (req.query.q || "").trim();
    const page = Math.max(1, parseInt(req.query.page) || 1);
    if (q.length < 2) return res.status(400).json({ error: "bad_query", detail: "q minimal 2 karakter" });
    try {
      const { html } = await fetcher.get(adapter().searchUrl(q, page));
      const $ = load(html);
      const results = adapter().parseSearch($);
      res.json({ query: q, page, has_next: $("a.nextpostslink, a.next.page-numbers").length > 0, results });
    } catch (e) { err(e, res); }
  });

  app.get("/api/v1/latest", rl(15), async (req, res) => {
    const page = Math.max(1, parseInt(req.query.page) || 1);
    try {
      const { html } = await fetcher.get(adapter().latestUrl(page));
      const { items, hasNext } = adapter().parseLatest(load(html));
      res.json({ page, has_next: hasNext, results: items });
    } catch (e) { err(e, res); }
  });

  app.get("/api/v1/popular", rl(15), async (req, res) => {
    const page = Math.max(1, parseInt(req.query.page) || 1);
    try {
      const { html } = await fetcher.get(adapter().popularUrl(page));
      const { items, hasNext } = adapter().parseLatest(load(html));
      res.json({ page, has_next: hasNext, results: items });
    } catch (e) { err(e, res); }
  });

  app.get("/api/v1/manga", rl(30), async (req, res) => {
    const id = (req.query.id || "").trim();
    if (!id) return res.status(400).json({ error: "bad_query", detail: "id wajib" });
    try {
      const { finalUrl, html } = await fetcher.get(adapter().mangaUrl(id));
      res.json(adapter().parseMangaDetail(load(html), id, finalUrl));
    } catch (e) { err(e, res); }
  });

  app.get("/api/v1/chapters", rl(20), async (req, res) => {
    const mangaId = (req.query.manga_id || "").trim();
    if (!mangaId) return res.status(400).json({ error: "bad_query", detail: "manga_id wajib" });
    try {
      const { html } = await fetcher.get(adapter().mangaUrl(mangaId));
      const { mangaTitle, chapters } = adapter().parseChapters(load(html), mangaId);
      res.json({ manga_id: mangaId, manga_title: mangaTitle, count: chapters.length, chapters });
    } catch (e) { err(e, res); }
  });

  app.get("/api/v1/chapter", rl(20), async (req, res) => {
    const id = (req.query.id || "").trim();
    const mangaId = (req.query.manga_id || "").trim();
    if (!id) return res.status(400).json({ error: "bad_query", detail: "id wajib" });
    try {
      const { finalUrl, html } = await fetcher.get(adapter().chapterUrl(id, mangaId));
      res.json(adapter().parseChapterImages(load(html), id, mangaId, finalUrl));
    } catch (e) { err(e, res); }
  });

  app.get("/api/v1/image", rl(60), async (req, res) => {
    const url = (req.query.url || "").trim();
    if (!url) return res.status(400).json({ error: "bad_query", detail: "url wajib" });
    try {
      const { data, ctype } = await fetcher.getImage(url);
      res.set("Content-Type", ctype).set("Cache-Control", "public, max-age=86400").send(data);
    } catch (e) { err(e, res); }
  });

  app.post("/api/v1/cache/clear", (_, res) => { fetcher.clearCache(); res.json({ ok: true }); });

  return app;
}
