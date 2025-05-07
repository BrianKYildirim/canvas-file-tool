from __future__ import annotations
import argparse
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.cookiejar import CookieJar
from threading import Event
from typing import Iterable, List, Dict, Optional
from urllib.parse import urlparse

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s %(levelname)s] %(message)s",
    datefmt="%I:%M%p",
)


# Helpers
def _parse_response(resp: urllib.response.addinfourl) -> Dict[str, str]:
    """Return a minimal dict describing the Canvas *file* resource."""
    content_type = resp.headers.get("Content-Type", "")
    body = resp.read().decode("utf-8", errors="replace")

    if "application/json" in content_type:
        return json.loads(body)

    if "text/html" in content_type:
        name_match = re.search(r"Download (.*?)</a>", body)
        url_match = re.search(r"<a href=\"([^\"]*?/files/\d+)", body)
        if not (name_match and url_match):
            raise ValueError("Unable to parse HTML response from Canvas")

        display_name = name_match.group(1)
        file_path = url_match.group(1)
        parsed = urlparse(resp.geturl())
        download_url = f"{parsed.scheme}://{parsed.netloc}{file_path}/download?download_frd=1"
        return {"display_name": display_name, "created_at": "", "url": download_url}

    raise ValueError(f"Unexpected content type: {content_type}")


def _file_id_stream(start: int, count: int) -> Iterable[int]:
    """Generate *count* file‑IDs below *start* (exclusive), descending."""
    for fid in range(start - 1, start - count - 1, -1):
        yield fid


# Core worker logic
def _fetch_file(
        file_id: int,
        base_url: str,
        opener: urllib.request.OpenerDirector,
        stop_event: Event,
) -> Optional[Dict[str, str]]:
    """Return file‑metadata dict on success, *None* on 404, raise on others."""
    if stop_event.is_set():
        return None

    url = f"{base_url}/{file_id}"
    try:
        with opener.open(url) as response:
            meta = _parse_response(response)
            logging.info("FOUND: %s", url)
            return {
                "id": file_id,
                "url": url,
                "display_name": meta.get("display_name"),
                "created_at": meta.get("created_at"),
                "download_url": meta.get("url"),
            }

    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        stop_event.set()
        raise
    except Exception:
        stop_event.set()
        raise


# Public API - `scan_canvas_files`
def scan_canvas_files(
        *,
        start_id: int,
        count: int,
        workers: int,
        base_url: str,
        cookies: str,
) -> List[Dict[str, str]]:
    """Threaded scan of Canvas file IDs below *start_id*.

    Parameters
    ----------
    start_id:   The file ID from which to start scanning (exclusive).
    count:      Number of IDs to inspect below *start_id*.
    workers:    Thread pool size (1‑32 recommended).
    base_url:   https://…/files  – *no* trailing slash.
    cookies:    Value for the `canvas_session` cookie.
    """
    stop_event = Event()

    # Re‑usable HTTP opener (keeps connections alive across threads)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    opener.addheaders = [
        ("Cookie", f"canvas_session={cookies}"),
        (
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        ),
    ]

    results: List[Dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(_fetch_file, fid, base_url, opener, stop_event): fid
            for fid in _file_id_stream(start_id, count)
        }

        for future in as_completed(future_map):
            fid = future_map[future]
            if stop_event.is_set():
                break  # abort processing once a fatal error has been signalled
            try:
                file_info = future.result()
                if file_info:
                    results.append(file_info)
            except urllib.error.HTTPError as err:
                logging.error("HTTP %s for file‑ID %d", err.code, fid)
            except Exception as exc:
                logging.error("Unexpected error for file‑ID %d → %s", fid, exc)

    results.sort(key=lambda r: r["id"], reverse=True)
    return results


# CLI
def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if not (parsed.scheme and parsed.netloc):
        raise argparse.ArgumentTypeError("Invalid URL format")

    if not re.search(r"files/\d+", url):
        raise argparse.ArgumentTypeError("URL must contain /files/<id>")
    return url


def _cli() -> None:
    env_token = os.getenv("CANVAS_SESSION")
    p = argparse.ArgumentParser(description="Canvas file sweeper (refactored)")
    p.add_argument("-u", "--url", type=_validate_url, required=True)
    p.add_argument("-n", "--num-files", type=int, default=10_000, metavar="INT")
    p.add_argument("-w", "--workers", type=int, default=16, choices=range(1, 33))
    p.add_argument("-s", "--canvas-session", default=env_token)
    args = p.parse_args()

    if not args.canvas_session:
        p.error("Canvas session token missing – use --canvas-session or CANVAS_SESSION env var")

    start_id = int(re.search(r"files/(\d+)", args.url).group(1))
    base_url = re.sub(r"files/\d+/?$", "files", args.url.rstrip("/"))

    logging.info("Scanning – start_id=%d, count=%d, workers=%d", start_id, args.num_files, args.workers)

    try:
        hits = scan_canvas_files(
            start_id=start_id,
            count=args.num_files,
            workers=args.workers,
            base_url=base_url,
            cookies=args.canvas_session,
        )
    except KeyboardInterrupt:
        logging.warning("Interrupted – partial results will be saved.")
        hits = []

    out_dir = "output"
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{time.strftime('%Y%m%d-%H%M%S')}-canvas-files.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(hits, f, indent=4)
    logging.info("Saved %d records → %s", len(hits), out_file)


if __name__ == "__main__":
    _cli()
