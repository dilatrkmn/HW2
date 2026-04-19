# HW2 - Multi-Agent Crawler + Search

## What this project is
A localhost web crawler/search system that provides:
- `/index` behavior via API/CLI to crawl from `origin` to depth `k`.
- `/search` behavior that returns `(relevant_url, origin_url, depth)`.
- Live status (queue depth, back pressure, job progress) while indexing continues.

## Run
```bash
python app.py serve --host 127.0.0.1 --port 8080
```
Open: `http://127.0.0.1:8080`

## CLI alternatives
```bash
python app.py index https://example.com 1
python app.py search example
python app.py reset
```

## API
### Start indexing
`POST /api/index`
```json
{"origin":"https://example.com","k":1}
```

### Search
`GET /api/search?query=example`

### Runtime state
`GET /api/state`

### Reset everything (clean DB + runtime)
`POST /api/reset`

## Architecture summary
- `crawler/crawler.py`
  - Worker-pool crawler using bounded queue for back pressure.
  - Global URL de-duplication.
  - Per-host delay throttling.
  - HTML parsing with Python `html.parser`.
- `crawler/storage.py`
  - SQLite schema for jobs, pages, discoveries.
  - Search query joins pages/discoveries/jobs.
- `app.py`
  - Lightweight HTTP server + static HTML UI.

## How search works while indexing is active
- As each page is fetched, title/body are written immediately to SQLite.
- Search reads committed rows, so users see newly indexed pages in near real-time.

## Resume after interruption
- Indexed page/discovery data is persisted in `data/crawler.db`.
- On restart, data remains searchable.
- (Current limitation) in-flight queue state is not restored automatically.

## Clean restart workflow
If you want to wipe everything and crawl from scratch:
1. CLI: run `python app.py reset`.
2. UI: click **Reset DB + Runtime**.
3. API: `POST /api/reset`.

## Notes on “surface similar to crawler repo”
The UI is intentionally minimal and practical:
- Start crawl form
- Search box + results table
- Live runtime/job state pane
