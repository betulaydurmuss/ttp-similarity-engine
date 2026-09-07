"""Download the MITRE ATT&CK Enterprise STIX bundle to ``data/raw/``.

The bundle is a single large JSON file (roughly 40 MB) published by MITRE at
:data:`ttp_similarity.config.ATTACK_STIX_URL`. It is downloaded once and cached;
every later stage reads from disk, so the pipeline is reproducible offline.

Run standalone::

    python -m ttp_similarity.data.stix_download            # cached if present
    python -m ttp_similarity.data.stix_download --force    # re-download

Owner: data module.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .. import config, paths


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
        RuntimeError: If the download fails or the response is not valid JSON.
    """
    destination = destination or paths.ATTACK_BUNDLE_PATH
    # TODO(data): if destination.exists() and not force -> log + return it.
    # TODO(data): stream with requests.get(url, stream=True,
    #   timeout=config.DOWNLOAD_TIMEOUT_SECONDS) writing
    #   config.DOWNLOAD_CHUNK_BYTES chunks to a ".part" file, then atomically
    #   rename onto `destination`, so an interrupted run never leaves a
    #   half-written bundle that later stages would happily parse.
    # TODO(data): raise_for_status(), then validate the first bytes parse as
    #   JSON and the object has type == "bundle".
    # TODO(data): write a sibling ".meta.json" with url, ETag/Last-Modified and
    #   download timestamp -- this is what feeds BuildManifest.attack_version.
    raise NotImplementedError("fetch_attack_bundle")


def read_bundle_version(bundle_path: Path | None = None) -> str | None:
    """Return the ATT&CK release version recorded in the bundle, if present.

    ATT&CK bundles carry an ``x-mitre-collection`` object whose ``x_mitre_version``
    identifies the release (e.g. ``"15.1"``). Used for
    :class:`~ttp_similarity.schema.BuildManifest`.

    Args:
        bundle_path: Bundle location; defaults to the cached raw path.

    Returns:
        Version string, or ``None`` when the bundle does not declare one.
    """
    # TODO(data): load the JSON, find the object with
    #   type == "x-mitre-collection", return its x_mitre_version.
    raise NotImplementedError("read_bundle_version")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m ttp_similarity.data.stix_download``."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download the bundle")
    parser.add_argument("--url", default=config.ATTACK_STIX_URL)
    args = parser.parse_args(argv)

    paths.ensure_base_dirs()
    destination = fetch_attack_bundle(url=args.url, force=args.force)
    print(f"bundle: {destination}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
