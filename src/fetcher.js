import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STATE_FILE = path.join(__dirname, "..", ".domain_state.json");

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";
const CACHE_TTL = 600_000; // 10 min
const MIN_DELAY = 1000;    // 1s politeness

const parentDomain = (host = "") => host.split(".").slice(-2).join(".");

export class DomainManager {
  constructor(initial, parent = "shinigami.asia") {
    this.configured = initial.replace(/\/$/, "");
    this.parent = parent;
    this.current = this.configured;
    this.rotated = false;
    this._load();
  }
  _load() {
    try {
      const data = JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
      const host = new URL(data.current).hostname;
      if (parentDomain(host) === this.parent) {
        this.current = data.current.replace(/\/$/, "");
        this.rotated = this.current !== this.configured;
      }
    } catch {}
  }
  _save() {
    try { fs.writeFileSync(STATE_FILE, JSON.stringify({ current: this.current })); } catch {}
  }
  base() { return this.current; }
  set(domain) {
    domain = domain.replace(/\/$/, "");
    const host = new URL(domain).hostname;
    if (parentDomain(host) !== this.parent) throw new Error(`domain must be under ${this.parent}`);
    this.current = domain;
    this.rotated = this.current !== this.configured;
    this._save();
  }
  observe(finalUrl) {
    let host;
    try { host = new URL(finalUrl).hostname; } catch { return false; }
    if (!host || parentDomain(host) !== this.parent) return false;
    const nb = `https://${host}`;
    if (nb !== this.current) {
      this.current = nb;
      this.rotated = this.current !== this.configured;
      this._save();
      return true;
    }
    return false;
  }
  info() { return { configured: this.configured, current: this.current, rotated: this.rotated }; }
}

export class FetchError extends Error {
  constructor(kind, detail = "") { super(`${kind}: ${detail}`); this.kind = kind; this.detail = detail; }
}

export class Fetcher {
  constructor(domains) {
    this.domains = domains;
    this.cache = new Map();
    this.last = new Map();
  }
  async _polite(host) {
    const wait = MIN_DELAY - (Date.now() - (this.last.get(host) || 0));
    if (wait > 0) await new Promise(r => setTimeout(r, wait));
    this.last.set(host, Date.now());
  }
  async get(url) {
    const hit = this.cache.get(url);
    if (hit && Date.now() - hit.ts < CACHE_TTL) return { finalUrl: hit.finalUrl, html: hit.html };
    const host = new URL(url).hostname;
    await this._polite(host);
    let res;
    try {
      res = await fetch(url, {
        redirect: "follow",
        headers: { "User-Agent": UA, "Accept-Language": "id-ID,id;q=0.9,en;q=0.8", "Referer": this.domains.base() + "/" },
        signal: AbortSignal.timeout(25000),
      });
    } catch (e) { throw new FetchError("NETWORK_ERROR", String(e).slice(0, 200)); }
    const finalUrl = res.url;
    this.domains.observe(finalUrl);
    const text = await res.text();
    const low = text.slice(0, 800).toLowerCase();
    if (res.status === 403 && (low.includes("cloudflare") || low.includes("just a moment") || low.includes("attention required")))
      throw new FetchError("BLOCKED_BY_CLOUDFLARE", "target diblokir Cloudflare dari IP server ini");
    if (res.status === 403) throw new FetchError("HTTP_403_FORBIDDEN", finalUrl);
    if (res.status === 404) throw new FetchError("NOT_FOUND", url);
    if (res.status >= 400) throw new FetchError(`HTTP_${res.status}`, finalUrl);
    this.cache.set(url, { ts: Date.now(), finalUrl, html: text });
    return { finalUrl, html: text };
  }
  async getImage(url) {
    let res;
    try {
      res = await fetch(url, {
        redirect: "follow",
        headers: { "User-Agent": UA, "Referer": this.domains.base() + "/" },
        signal: AbortSignal.timeout(30000),
      });
    } catch (e) { throw new FetchError("NETWORK_ERROR", String(e).slice(0, 200)); }
    if (res.status >= 400) throw new FetchError(`HTTP_${res.status}`, url);
    const buf = Buffer.from(await res.arrayBuffer());
    return { data: buf, ctype: res.headers.get("content-type") || "image/jpeg" };
  }
  clearCache() { this.cache.clear(); }
}
