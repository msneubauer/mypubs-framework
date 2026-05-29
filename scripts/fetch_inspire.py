#!/usr/bin/env python3
"""Fetch INSPIRE records as JSON, one year per cache file.

The fetcher uses small paged requests and falls back to month-sized queries
because large yearly INSPIRE responses can return transient 502s.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import OrderedDict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://inspirehep.net/api/literature"


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def build_url(query: str, date_expr: str, size: int = 25, page: int = 1) -> str:
    params = {
        "sort": "mostrecent",
        "size": str(size),
        "page": str(page),
        "q": f"{query} and date {date_expr}",
    }
    return f"{API_URL}?{urlencode(params)}"


def fetch_json_url(url: str, timeout: int, retries: int) -> dict:
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "mypubs-framework/0.3"})
    retryable = {429, 500, 502, 503, 504}
    for attempt in range(1, retries + 1):
        try:
            with urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code not in retryable or attempt == retries:
                raise
            wait = min(45, 2 ** attempt)
            print(f"  HTTP {exc.code}; retrying in {wait}s ({attempt}/{retries})", file=sys.stderr)
            time.sleep(wait)
        except URLError as exc:
            if attempt == retries:
                raise
            wait = min(45, 2 ** attempt)
            print(f"  network error {exc.reason}; retrying in {wait}s ({attempt}/{retries})", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def total_hits(data: dict) -> int:
    total = data.get("hits", {}).get("total", 0)
    if isinstance(total, dict):
        return int(total.get("value", 0) or 0)
    return int(total or 0)


def hit_id(hit: dict) -> str:
    return str(hit.get("id") or hit.get("metadata", {}).get("control_number") or json.dumps(hit, sort_keys=True))


def fetch_date_expr(query: str, date_expr: str, size: int, timeout: int, retries: int) -> dict:
    all_hits = []
    total = None
    page = 1
    last_data = {"hits": {"hits": [], "total": 0}}
    while True:
        url = build_url(query, date_expr, size=size, page=page)
        print(f"  {date_expr} page {page}: {url}")
        data = fetch_json_url(url, timeout=timeout, retries=retries)
        last_data = data
        hits = data.get("hits", {}).get("hits", [])
        if total is None:
            total = total_hits(data)
            print(f"  {date_expr} total hits: {total}")
        all_hits.extend(hits)
        if not hits or len(all_hits) >= total:
            data.setdefault("hits", {})["hits"] = all_hits
            data["hits"]["total"] = total
            return data
        page += 1
        time.sleep(0.25)


def combine_results(results: list[dict]) -> dict:
    combined = dict(results[0]) if results else {"hits": {}}
    by_id: OrderedDict[str, dict] = OrderedDict()
    for result in results:
        for hit in result.get("hits", {}).get("hits", []):
            by_id.setdefault(hit_id(hit), hit)
    combined.setdefault("hits", {})["hits"] = list(by_id.values())
    combined["hits"]["total"] = len(by_id)
    return combined


def fetch_year(query: str, year: int, size: int, timeout: int, retries: int, month_fallback: bool) -> dict:
    try:
        return fetch_date_expr(query, str(year), size=size, timeout=timeout, retries=retries)
    except (HTTPError, URLError) as exc:
        if not month_fallback:
            raise
        print(f"  yearly query failed for {year}: {exc}", file=sys.stderr)
        print(f"  falling back to month-sized queries for {year}", file=sys.stderr)

    monthly = []
    for month in range(12, 0, -1):
        date_expr = f"{year}-{month:02d}"
        monthly.append(fetch_date_expr(query, date_expr, size=size, timeout=timeout, retries=retries))
        time.sleep(0.5)
    return combine_results(monthly)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--force", action="store_true", help="refetch existing cache files")
    parser.add_argument("--start-year", type=int, help="override config start_year")
    parser.add_argument("--end-year", type=int, help="override config end_year")
    parser.add_argument("--year", type=int, help="fetch one year only")
    parser.add_argument("--size", type=int, default=25, help="page size for INSPIRE requests")
    parser.add_argument("--timeout", type=int, default=90, help="per-request timeout in seconds")
    parser.add_argument("--retries", type=int, default=5, help="number of tries per page")
    parser.add_argument("--no-month-fallback", action="store_true", help="do not split failed yearly queries by month")
    args = parser.parse_args()

    root = Path.cwd()
    cfg = load_config(root / args.config)
    raw_dir = root / cfg["raw_dir"]
    raw_dir.mkdir(parents=True, exist_ok=True)

    start = args.start_year if args.start_year is not None else int(cfg["start_year"])
    end = args.end_year if args.end_year is not None else int(cfg["end_year"])
    if args.year is not None:
        start = end = args.year
    if start > end:
        start, end = end, start
    query = cfg["author_query"]

    missing_years = []

    for year in range(end, start - 1, -1):
        out = raw_dir / f"inspire-{year}.json"
        if out.exists() and not args.force:
            print(f"cache exists: {out}")
            continue
        print(f"fetching {year}")
        try:
            data = fetch_year(
                query,
                year,
                size=args.size,
                timeout=args.timeout,
                retries=args.retries,
                month_fallback=not args.no_month_fallback,
            )
        except (HTTPError, URLError) as exc:
            print(f"warning: failed to fetch {year}: {exc}", file=sys.stderr)
            if out.exists():
                print(f"  keeping existing cache: {out}")
                continue
            print("  no cache for this year; will report at end", file=sys.stderr)
            missing_years.append(year)
            continue
        out.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        print(f"  wrote {out} ({total_hits(data)} hits)")
        time.sleep(0.5)

    if missing_years:
        years = ", ".join(str(year) for year in missing_years)
        print(f"error: failed to fetch uncached years: {years}", file=sys.stderr)
        print("rerun make fetch later; cached years will be skipped", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
