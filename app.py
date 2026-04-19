from __future__ import annotations

import argparse
import json
import signal
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from crawler.crawler import CrawlerEngine
from crawler.storage import Storage

storage = Storage()
engine = CrawlerEngine(storage=storage, workers=6, max_queue_size=1200, per_host_delay_sec=0.2)
engine.start()


INDEX_HTML = """<!doctype html>
<html>
<head>
  <meta charset='utf-8' />
  <title>HW2 Multi-Agent Crawler</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; background: #fafafa; }
    .row { display: flex; gap: 20px; align-items: flex-start; }
    .card { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 16px; width: 48%; }
    input, button { padding: 8px; margin: 4px 0; }
    input { width: 100%; }
    pre { background: #f0f0f0; padding: 10px; overflow: auto; max-height: 260px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid #e8e8e8; text-align: left; padding: 6px; font-size: 14px; }
  </style>
</head>
<body>
  <h2>HW2 Multi-Agent Web Crawler + Search</h2>
  <div class='row'>
    <div class='card'>
      <h3>Start Index Job</h3>
      <label>Origin URL</label>
      <input id='origin' value='https://example.com' />
      <label>Max Depth (k)</label>
      <input id='depth' type='number' min='0' max='6' value='1' />
      <button onclick='startJob()'>Start</button>
      <button onclick='resetSystem()' style='margin-left:6px;background:#ffeaea;'>Reset DB + Runtime</button>
      <p id='startStatus'></p>

      <h3>Search</h3>
      <label>Query</label>
      <input id='query' placeholder='Search text' />
      <button onclick='doSearch()'>Search</button>
      <div id='searchResults'></div>
    </div>

    <div class='card'>
      <h3>System State</h3>
      <button onclick='refreshState()'>Refresh</button>
      <pre id='state'></pre>
      <h4>Jobs</h4>
      <div id='jobs'></div>
    </div>
  </div>

<script>
async function startJob() {
  const origin = document.getElementById('origin').value;
  const depth = parseInt(document.getElementById('depth').value, 10);
  const res = await fetch('/api/index', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({origin, k: depth})});
  const data = await res.json();
  document.getElementById('startStatus').innerText = JSON.stringify(data);
  refreshState();
}

async function doSearch() {
  const query = document.getElementById('query').value;
  const res = await fetch('/api/search?query=' + encodeURIComponent(query));
  const data = await res.json();
  let html = '<table><tr><th>Relevant URL</th><th>Origin</th><th>Depth</th></tr>';
  for (const row of data.results) {
    html += `<tr><td><a href='${row.relevant_url}' target='_blank'>${row.relevant_url}</a></td><td>${row.origin_url}</td><td>${row.depth}</td></tr>`;
  }
  html += '</table>';
  document.getElementById('searchResults').innerHTML = html;
}

async function refreshState() {
  const res = await fetch('/api/state');
  const data = await res.json();
  document.getElementById('state').innerText = JSON.stringify(data.runtime, null, 2);

  let jobs = '<table><tr><th>ID</th><th>Status</th><th>Origin</th><th>k</th><th>Discovered</th><th>Fetched</th></tr>';
  for (const j of data.jobs) {
    jobs += `<tr><td>${j.id}</td><td>${j.status}</td><td>${j.origin_url}</td><td>${j.max_depth}</td><td>${j.pages_discovered}</td><td>${j.pages_fetched}</td></tr>`;
  }
  jobs += '</table>';
  document.getElementById('jobs').innerHTML = jobs;
}

async function resetSystem() {
  if (!confirm('This will delete all jobs/pages and clear runtime state. Continue?')) return;
  const res = await fetch('/api/reset', {method:'POST'});
  const data = await res.json();
  document.getElementById('startStatus').innerText = JSON.stringify(data);
  document.getElementById('searchResults').innerHTML = '';
  refreshState();
}

setInterval(refreshState, 3000);
refreshState();
</script>
</body>
</html>
"""


class AppHandler(BaseHTTPRequestHandler):
    def _json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length)
        return json.loads(data.decode("utf-8")) if data else {}

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            content = INDEX_HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if parsed.path == "/api/search":
            qs = parse_qs(parsed.query)
            query = qs.get("query", [""])[0].strip()
            if not query:
                self._json({"results": []})
                return
            self._json({"results": storage.search(query)})
            return

        if parsed.path == "/api/state":
            self._json(
                {
                    "runtime": engine.get_runtime_state(),
                    "jobs": storage.get_jobs(),
                    "pages": storage.count_pages_by_status(),
                }
            )
            return

        self._json({"error": "Not Found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/index":
            payload = self._read_json()
            origin = str(payload.get("origin", "")).strip()
            k = int(payload.get("k", 0))
            if not origin:
                self._json({"error": "origin is required"}, status=400)
                return
            if k < 0:
                self._json({"error": "k must be >= 0"}, status=400)
                return
            job_id = engine.enqueue_job(origin, k)
            self._json({"job_id": job_id, "status": "running"}, status=202)
            return

        if parsed.path == "/api/reset":
            engine.reset_runtime_state()
            storage.reset_all()
            self._json({"status": "reset_complete"})
            return

        self._json({"error": "Not Found"}, status=404)


def run_server(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), AppHandler)

    def shutdown(*_: object) -> None:
        server.shutdown()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"Server running at http://{host}:{port}")
    try:
        server.serve_forever()
    finally:
        engine.stop()


def run_cli_index(origin: str, k: int) -> None:
    job_id = engine.enqueue_job(origin, k)
    print(f"Started job={job_id}")


def run_cli_search(query: str) -> None:
    for row in storage.search(query):
        print((row["relevant_url"], row["origin_url"], row["depth"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="HW2 crawler + search")
    sub = parser.add_subparsers(dest="cmd")

    srv = sub.add_parser("serve", help="run web UI + API")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8080)

    index_cmd = sub.add_parser("index", help="enqueue an index job")
    index_cmd.add_argument("origin")
    index_cmd.add_argument("k", type=int)

    search_cmd = sub.add_parser("search", help="run a search query")
    search_cmd.add_argument("query")
    sub.add_parser("reset", help="clear DB and in-memory crawler state")

    args = parser.parse_args()
    if args.cmd == "serve":
        run_server(args.host, args.port)
    elif args.cmd == "index":
        run_cli_index(args.origin, args.k)
    elif args.cmd == "search":
        run_cli_search(args.query)
    elif args.cmd == "reset":
        engine.reset_runtime_state()
        storage.reset_all()
        print("Reset complete: DB cleared and runtime state restarted.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
