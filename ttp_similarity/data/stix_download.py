"""Download the MITRE ATT&CK Enterprise STIX bundle to ``data/raw/``.

The bundle is a single large JSON file (~50 MB) published by MITRE at
:data:`ttp_similarity.config.ATTACK_STIX_URL`. It is downloaded once and cached;
every later stage reads from disk, so the pipeline is reproducible offline.

Alongside the bundle a sidecar ``enterprise-attack.meta.json`` records the source
URL, the download timestamp, the server ETag, the file size, a SHA-256 checksum
and the ATT&CK release version. That sidecar is what lets a report say
"ATT&CK v18.1, downloaded 2026-09-07" rather than "a recent ATT&CK".

Run standalone::

    python -m ttp_similarity.data.stix_download            # cached if present
    python -m ttp_similarity.data.stix_download --force    # re-download

Owner: data module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .. import config, paths


def _sha256(path: Path) -> str:
    """SHA-256 of a file, streamed so a 50 MB bundle never lands in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(config.DOWNLOAD_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_bundle_version(bundle_path: Path | None = None) -> str | None:
    """Return the ATT&CK release version recorded in the bundle, if present.

    ATT&CK bundles carry an ``x-mitre-collection`` object whose ``x_mitre_version``
    identifies the release (e.g. ``"18.1"``). Used for
    :class:`~ttp_similarity.schema.BuildManifest`.

    Args:
        bundle_path: Bundle location; defaults to the cached raw path.

    Returns:
        Version string, or ``None`` when the bundle does not declare one.
    """
    bundle_path = bundle_path or paths.ATTACK_BUNDLE_PATH
    if not bundle_path.exists():
        return None
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    for item in payload.get("objects", []):
        if item.get("type") == "x-mitre-collection":
            version = item.get("x_mitre_version")
            if version:
                return str(version)
    return None


def write_bundle_metadata(
    bundle_path: Path,
    *,
    url: str,
    etag: str | None = None,
    last_modified: str | None = None,
    meta_path: Path | None = None,
) -> Path:
    """Write the provenance sidecar next to a downloaded bundle.

    Args:
        bundle_path: The bundle the metadata describes.
        url: Source URL it came from.
        etag: Server ETag, when the response carried one.
        last_modified: Server ``Last-Modified`` header, when present.
        meta_path: Destination; defaults to
            :data:`ttp_similarity.paths.ATTACK_BUNDLE_META_PATH`.

    Returns:
        Path to the sidecar that was written.
    """
    meta_path = meta_path or paths.ATTACK_BUNDLE_META_PATH
    metadata: dict[str, Any] = {
        "url": url,
        "attack_release_ref": config.ATTACK_RELEASE,
        "attack_version": read_bundle_version(bundle_path),
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "size_bytes": bundle_path.stat().st_size,
        "sha256": _sha256(bundle_path),
        "etag": etag,
        "last_modified": last_modified,
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta_path


def read_bundle_metadata(meta_path: Path | None = None) -> dict[str, Any]:
    """Read the provenance sidecar. Returns ``{}`` when it does not exist."""
    meta_path = meta_path or paths.ATTACK_BUNDLE_META_PATH
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def fetch_attack_bundle(
    destination: Path | None = None,
    *,
    url: str = config.ATTACK_STIX_URL,
    force: bool = False,
) -> Path:
    """Download the ATT&CK Enterprise STIX bundle, or reuse the cached copy.

    Args:
        destination: Where to write the bundle. Defaults to
            :data:`ttp_similarity.paths.ATTACK_BUNDLE_PATH`.
        url: Source URL. Override to pin a specific ATT&CK release.
        force: Re-download even when a cached file exists.

    Returns:
        Path to the JSON bundle on disk.

    Raises:
        RuntimeError: If the download fails or the response is not a STIX bundle.
    """
    destination = destination or paths.ATTACK_BUNDLE_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not force:
        print(f"[download] cached: {destination} ({destination.stat().st_size:,} bytes)")
        if not paths.ATTACK_BUNDLE_META_PATH.exists():
            # Cached from an older run that predates the sidecar; backfill it so
            # the manifest can still report a version.
            write_bundle_metadata(destination, url=url)
        return destination

    # Download to a ".part" file and rename only on success. An interrupted run
    # must never leave a truncated bundle that the parser would happily read.
    partial = destination.with_suffix(destination.suffix + ".part")
    print(f"[download] fetching {url}")
    try:
        response = requests.get(
            url, stream=True, timeout=config.DOWNLOAD_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=config.DOWNLOAD_CHUNK_BYTES):
                if chunk:
                    handle.write(chunk)
    except requests.RequestException as error:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"ATT&CK bundle download failed: {error}") from error

    # Validate before committing: a proxy error page is also a 200 response.
    try:
        payload = json.loads(partial.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"downloaded file is not valid JSON: {error}") from error
    if payload.get("type") != "bundle":
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"downloaded JSON is not a STIX bundle (type={payload.get('type')!r})"
        )

    partial.replace(destination)
    write_bundle_metadata(
        destination,
        url=url,
        etag=response.headers.get("ETag"),
        last_modified=response.headers.get("Last-Modified"),
    )
    print(f"[download] saved: {destination} ({destination.stat().st_size:,} bytes)")
    return destination


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m ttp_similarity.data.stix_download``."""
    parser = argparse.ArgumentParser(description="Download the ATT&CK Enterprise bundle.")
    parser.add_argument("--force", action="store_true", help="re-download the bundle")
    parser.add_argument("--url", default=config.ATTACK_STIX_URL)
    args = parser.parse_args(argv)

    paths.ensure_base_dirs()
    destination = fetch_attack_bundle(url=args.url, force=args.force)
    metadata = read_bundle_metadata()
    print(f"bundle        : {destination}")
    print(f"ATT&CK version: {metadata.get('attack_version') or 'bilinmiyor'}")
    print(f"downloaded_at : {metadata.get('downloaded_at')}")
    print(f"sha256        : {metadata.get('sha256')}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
