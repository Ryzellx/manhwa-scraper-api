# Manhwa Scraper API (Node.js)

REST API scraper manhwa berbahasa Indonesia — **Shinigami** (WordPress Madara).
Built with Node.js + Express + Cheerio.

> ⚠️ **PENTING — WAJIB PAKAI PROXY**
> Situs target dilindungi **Cloudflare** dan memblokir IP datacenter
> (VPS, Vercel, Railway, dsb). API akan mengembalikan `502 upstream_blocked`
> kalau dijalankan dari IP yang diblokir.
>
> **Solusi:** jalankan dari IP residensial/bersih, atau set proxy:
> ```bash
> export HTTP_PROXY=http://user:pass@proxy-host:port
> export HTTPS_PROXY=http://user:pass@proxy-host:port
> npm start
> ```
> Node.js otomatis memakai `HTTP_PROXY`/`HTTPS_PROXY` via `fetch`.
> Proxy residensial murah (~$5–15/bulan) sudah cukup.

## Fitur

- 🔍 Search manga
- 🆕 Latest updates & 🔥 popular
- 📖 Detail manga (author, artist, status, genre, sinopsis)
- 📚 Daftar chapter
- 🖼️ Gambar chapter + navigasi prev/next
- 🔄 **Auto domain rotation** — domain shinigami suka ganti (`11.` → `12.` → ...);
  API otomatis mengikuti redirect dan menyimpan domain aktif
- 🖼️ Image proxy (atasi hotlink protection)
- ⏱️ Rate limit + cache 10 menit

## Quick Start

```bash
npm install
npm start
# API jalan di http://localhost:8078
```

Deploy ke Vercel: connect repo ini, auto-detect via `api/index.js`.

## Endpoint

| Method | Path | Deskripsi |
|---|---|---|
| GET | `/health` | Status + domain aktif |
| GET | `/api/v1/domain` | Lihat domain aktif & status rotasi |
| POST | `/api/v1/domain` | Set manual domain |
| GET | `/api/v1/search?q=&page=` | Cari manga |
| GET | `/api/v1/latest?page=` | Update terbaru |
| GET | `/api/v1/popular?page=` | Paling populer |
| GET | `/api/v1/manga?id=` | Detail manga (slug/URL) |
| GET | `/api/v1/chapters?manga_id=` | Daftar chapter |
| GET | `/api/v1/chapter?id=&manga_id=` | Gambar chapter |
| GET | `/api/v1/image?url=` | Proxy gambar |
| POST | `/api/v1/cache/clear` | Bersihkan cache |

## Domain Rotation

Setiap request mengikuti redirect; kalau URL final pindah ke `*.shinigami.asia`
yang baru, API otomatis memakai domain itu dan menyimpannya ke `.domain_state.json`.

```bash
curl https://<deploy>/api/v1/domain
# {"configured":"https://11.shinigami.asia","current":"https://12.shinigami.asia","rotated":true}
```

## Rate Limit

| Endpoint | Limit |
|---|---|
| Global | 60/menit |
| search, manga | 30/menit |
| chapters, chapter | 20/menit |
| latest, popular | 15/menit |
| image | 60/menit |
