from crawler.storage import Storage


def test_search_triples_roundtrip() -> None:
    db = Storage(':memory:')
    job_id = db.create_job('https://example.com', 1)
    page_id = db.upsert_page_shell('https://example.com')
    assert db.save_discovery(job_id, page_id, 0, None)
    db.mark_page_fetched(page_id, 'Example Domain', 'this is example body')
    db.increment_job_fetched(job_id)

    rows = db.search('example')
    assert rows
    first = rows[0]
    assert first['relevant_url'] == 'https://example.com'
    assert first['origin_url'] == 'https://example.com'
    assert first['depth'] == 0


def test_reset_all_clears_tables() -> None:
    db = Storage(':memory:')
    job_id = db.create_job('https://example.com', 1)
    page_id = db.upsert_page_shell('https://example.com')
    assert db.save_discovery(job_id, page_id, 0, None)
    db.mark_page_fetched(page_id, 'Example', 'body')
    db.increment_job_fetched(job_id)
    assert db.get_jobs()
    assert db.search('example')

    db.reset_all()

    assert db.get_jobs() == []
    assert db.search('example') == []
    assert db.count_pages_by_status() == {'ok': 0, 'pending': 0, 'error': 0}
