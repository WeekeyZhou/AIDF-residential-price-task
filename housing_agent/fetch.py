"""Download raw payloads and keep them as immutable, checksummed snapshots.

Layout:  <raw_root>/<indicator_id>/<UTC timestamp>_<sha8>.json       exact bytes
         <raw_root>/<indicator_id>/<UTC timestamp>_<sha8>.meta.json  provenance
Snapshots are never overwritten or edited; a re-download adds a new file.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import Config, Indicator

USER_AGENT = "Mozilla/5.0 (compatible; housing-indicator-agent/1.0)"
RETRY_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class Snapshot:
    indicator_id: str
    path: Path
    sha256: str
    retrieved_at: str  # ISO 8601, UTC
    url: str

    def read(self) -> bytes:
        data = self.path.read_bytes()
        if hashlib.sha256(data).hexdigest() != self.sha256:
            raise FetchError(f"snapshot {self.path.name} does not match its recorded checksum")
        return data


def build_request(cfg: Config, ind: Indicator) -> tuple[str, dict]:
    params = {"limit": cfg.limit, "sortBy": "key desc"}
    if ind.series_no:
        params["seriesNoORrowNo"] = ind.series_no
    return f"{cfg.base_url}/{ind.table}", params


def download(cfg: Config, ind: Indicator, raw_root: Path, session=None,
             retries: int = 3, backoff: float = 2.0) -> Snapshot:
    """Fetch one indicator and store the response. Raises FetchError."""
    session = session or requests.Session()
    url, params = build_request(cfg, ind)
    last_error = "no attempt made"
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, params=params, timeout=30,
                               headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if resp.status_code == 200:
                return _store(ind.id, resp.content, resp.url, resp.status_code, raw_root)
            last_error = f"HTTP {resp.status_code}"
            if resp.status_code not in RETRY_STATUS:
                break  # a 4xx will not fix itself
        if attempt < retries:
            time.sleep(backoff ** attempt)
    raise FetchError(f"{ind.id}: download failed after {attempt} attempt(s): {last_error}")


def _store(indicator_id: str, content: bytes, url: str, status: int, raw_root: Path) -> Snapshot:
    now = datetime.now(timezone.utc)
    sha = hashlib.sha256(content).hexdigest()
    folder = raw_root / indicator_id
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}_{sha[:8]}"
    path = folder / f"{stem}.json"
    path.write_bytes(content)
    meta = {
        "indicator_id": indicator_id,
        "url": url,
        "http_status": status,
        "retrieved_at": now.isoformat(timespec="microseconds"),
        "bytes": len(content),
        "sha256": sha,
        "file": path.name,
    }
    (folder / f"{stem}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return Snapshot(indicator_id, path, sha, meta["retrieved_at"], url)


def list_snapshots(raw_root: Path, indicator_id: str) -> list[Snapshot]:
    """All stored snapshots for an indicator, oldest first."""
    out = []
    for meta_path in sorted((raw_root / indicator_id).glob("*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        out.append(Snapshot(indicator_id, meta_path.parent / meta["file"], meta["sha256"],
                            meta["retrieved_at"], meta["url"]))
    return out


def find_snapshot(raw_root: Path, indicator_id: str, sha256: str, file: str = "") -> Snapshot:
    """The snapshot recorded in a manifest. The same content can be downloaded more than once,
    so the file name is matched first and the checksum alone is only a fallback."""
    snaps = [s for s in list_snapshots(raw_root, indicator_id) if s.sha256 == sha256]
    for snap in snaps:
        if file.endswith(snap.path.name):
            return snap
    if snaps:
        return snaps[0]
    raise FetchError(f"{indicator_id}: no stored snapshot with sha256 {sha256[:12]}")
