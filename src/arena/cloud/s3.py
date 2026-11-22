"""Upload a directory to an S3 bucket (T292): the built site or the open-data exports.

Used with the bucket of `infra/aws` (CloudFront serves it) or any S3-compatible endpoint.
Credentials come from the standard AWS chain (environment, profile, role); nothing is read from or
written to the repository. Behaviour that matters in production:

- content types are guessed from the file name, so a browser renders HTML and CSS correctly;
- HTML is cached for a minute, everything else for a day (the site changes every few hours);
- a file whose content did not change (same MD5 as the stored ETag) is skipped;
- `prune` deletes objects under the prefix that no longer exist locally, `dry_run` only reports.
"""

from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CACHE_HTML = "public, max-age=60"
CACHE_OTHER = "public, max-age=86400"


@dataclass
class UploadReport:
    """What an upload did (or, with dry_run, would do)."""

    uploaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)


def content_type(path: Path) -> str:
    """MIME type from the file name; unknown names are served as bytes."""
    guess, _ = mimetypes.guess_type(path.name)
    return guess or "application/octet-stream"


def md5_hex(path: Path) -> str:
    """MD5 of a file (the ETag S3 gives single-part objects)."""
    h = hashlib.md5(usedforsecurity=False)  # an S3 convention, not a security use
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _existing(client: Any, bucket: str, prefix: str) -> dict[str, str]:
    """{key: etag without quotes} of the objects under a prefix."""
    out: dict[str, str] = {}
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            out[obj["Key"]] = str(obj["ETag"]).strip('"')
    return out


def upload_dir(
    client: Any,
    bucket: str,
    root: Path,
    prefix: str = "",
    *,
    prune: bool = False,
    dry_run: bool = False,
) -> UploadReport:
    """Upload every file under `root` to `bucket`/`prefix`; see the module docstring."""
    if not root.is_dir():
        raise ValueError(f"{root} is not a directory")
    prefix = prefix.strip("/")
    pre = f"{prefix}/" if prefix else ""
    have = _existing(client, bucket, pre)
    report = UploadReport()
    local: set[str] = set()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        key = pre + path.relative_to(root).as_posix()
        local.add(key)
        if have.get(key) == md5_hex(path):
            report.skipped.append(key)
            continue
        report.uploaded.append(key)
        if dry_run:
            continue
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=path.read_bytes(),
            ContentType=content_type(path),
            CacheControl=CACHE_HTML if path.suffix == ".html" else CACHE_OTHER,
        )
    if prune:
        for key in sorted(set(have) - local):
            report.deleted.append(key)
            if not dry_run:
                client.delete_object(Bucket=bucket, Key=key)
    return report
