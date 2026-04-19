from __future__ import annotations

import json
import queue
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser

from .storage import Storage


class LinkAndTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.title = ""
        self._in_title = False
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            for key, value in attrs:
                if key == "href" and value:
                    self.links.append(value.strip())
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data.strip()
        stripped = data.strip()
        if stripped:
            self.text_parts.append(stripped)


@dataclass
class CrawlTask:
    job_id: int
    origin_url: str
    url: str
    depth: int
    max_depth: int
    discovered_from: str | None


class CrawlerEngine:
    def __init__(
        self,
        storage: Storage,
        workers: int = 6,
        max_queue_size: int = 2000,
        per_host_delay_sec: float = 0.25,
    ) -> None:
        self.storage = storage
        self.workers = workers
        self.queue: queue.Queue[CrawlTask] = queue.Queue(maxsize=max_queue_size)
        self.per_host_delay_sec = per_host_delay_sec
        self._threads: list[threading.Thread] = []
        self._running = threading.Event()
        self._global_seen_lock = threading.Lock()
        self._global_seen_urls: set[str] = set()
        self._host_last_seen: dict[str, float] = {}
        self._host_lock = threading.Lock()
        self._dropped_on_full = 0

    def start(self) -> None:
        if self._running.is_set():
            return
        self._running.set()
        for i in range(self.workers):
            thread = threading.Thread(target=self._worker, name=f"crawler-{i}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self._running.clear()
        for _ in self._threads:
            self.queue.put(
                CrawlTask(-1, "", "", 0, 0, None)
            )
        for thread in self._threads:
            thread.join(timeout=2)
        self._threads.clear()

    def enqueue_job(self, origin_url: str, max_depth: int) -> int:
        job_id = self.storage.create_job(origin_url=origin_url, max_depth=max_depth)
        normalized = self._normalize_url(origin_url, origin_url)
        self._enqueue_if_new(
            CrawlTask(job_id, origin_url, normalized, 0, max_depth, None),
            allow_duplicate=False,
        )
        return job_id

    def _enqueue_if_new(self, task: CrawlTask, allow_duplicate: bool) -> bool:
        if not task.url:
            return False
        already_seen = False
        # A URL may be discovered by many jobs, but should be fetched only once globally.
        with self._global_seen_lock:
            already_seen = (not allow_duplicate) and (task.url in self._global_seen_urls)
            if not already_seen:
                try:
                    self.queue.put_nowait(task)
                except queue.Full:
                    self._dropped_on_full += 1
                    return False
                if not allow_duplicate:
                    self._global_seen_urls.add(task.url)

        page_id = self.storage.upsert_page_shell(task.url)
        created = self.storage.save_discovery(task.job_id, page_id, task.depth, task.discovered_from)
        return created or already_seen

    def _worker(self) -> None:
        while self._running.is_set():
            task = self.queue.get()
            try:
                if task.job_id == -1:
                    return
                page_id = self.storage.upsert_page_shell(task.url)
                self._throttle_host(task.url)
                html = self._fetch(task.url)
                parser = LinkAndTextParser()
                parser.feed(html)
                body = " ".join(parser.text_parts)[:80000]
                self.storage.mark_page_fetched(page_id, parser.title[:500], body)
                self.storage.increment_job_fetched(task.job_id)
                if task.depth < task.max_depth:
                    for raw_link in parser.links[:2000]:
                        child = self._normalize_url(task.url, raw_link)
                        if not child:
                            continue
                        child_task = CrawlTask(
                            task.job_id,
                            task.origin_url,
                            child,
                            task.depth + 1,
                            task.max_depth,
                            task.url,
                        )
                        self._enqueue_if_new(child_task, allow_duplicate=False)
            except Exception as exc:  # noqa: BLE001
                if task.job_id != -1:
                    page_id = self.storage.upsert_page_shell(task.url)
                    self.storage.mark_page_error(page_id, str(exc))
                    self.storage.increment_job_fetched(task.job_id)
            finally:
                self.queue.task_done()
                self._refresh_job_completion(task.job_id)

    def _refresh_job_completion(self, job_id: int) -> None:
        if job_id <= 0:
            return
        jobs = self.storage.get_jobs()
        match = next((j for j in jobs if j["id"] == job_id), None)
        if not match:
            return
        if match["status"] != "running":
            return
        if match["pages_discovered"] > 0 and match["pages_discovered"] == match["pages_fetched"]:
            self.storage.set_job_status(job_id, "completed")

    def _normalize_url(self, base: str, maybe_relative: str) -> str:
        joined = urllib.parse.urljoin(base, maybe_relative)
        parsed = urllib.parse.urlparse(joined)
        if parsed.scheme not in {"http", "https"}:
            return ""
        fragmentless = parsed._replace(fragment="")
        return urllib.parse.urlunparse(fragmentless)

    def _fetch(self, url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "HW2Crawler/1.0 (+https://localhost)",
                "Accept": "text/html,application/xhtml+xml",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as response:  # nosec B310
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                raise ValueError(f"Unsupported content-type: {content_type}")
            data = response.read(1_000_000)
        return data.decode("utf-8", errors="ignore")

    def _throttle_host(self, url: str) -> None:
        host = urllib.parse.urlparse(url).netloc
        if not host:
            return
        while True:
            with self._host_lock:
                last = self._host_last_seen.get(host, 0.0)
                wait = self.per_host_delay_sec - (time.time() - last)
                if wait <= 0:
                    self._host_last_seen[host] = time.time()
                    return
            time.sleep(min(wait, 0.05))

    def get_runtime_state(self) -> dict:
        return {
            "workers": self.workers,
            "queue_depth": self.queue.qsize(),
            "queue_capacity": self.queue.maxsize,
            "back_pressure_active": self.queue.qsize() > int(self.queue.maxsize * 0.8),
            "dropped_on_full": self._dropped_on_full,
            "seen_urls": len(self._global_seen_urls),
            "running": self._running.is_set(),
            "timestamp": time.time(),
        }

    def dumps_state(self) -> str:
        return json.dumps(self.get_runtime_state(), indent=2)

    def reset_runtime_state(self) -> None:
        """Clear in-memory queue + counters for a fresh run."""
        self.stop()
        while True:
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except queue.Empty:
                break
        with self._global_seen_lock:
            self._global_seen_urls.clear()
        with self._host_lock:
            self._host_last_seen.clear()
        self._dropped_on_full = 0
        self.start()
