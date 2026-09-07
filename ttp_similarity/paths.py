"""Canonical on-disk locations for every artefact the pipeline produces.

Nothing in this project passes DataFrames between modules in memory. Each stage
writes files, the next stage reads them. This module is the single place where
those file names live, so that the ``data`` / ``engine`` / ``evaluation`` / ``app``
owners never have to agree on a path in a chat message.

Layout::

    <repo>/
      data/
        raw/                      downloaded, untouched STIX bundle
        interim/                  optional scratch space for the data module
        processed/<dataset>/      the module contract lives here
        mock/                     synthetic fixtures (see data.mock_dataset)
      outputs/
        figures/<dataset>/        rendered plots
        reports/<dataset>/        evaluation reports, query logs

``<dataset>`` is a workspace name -- ``"mitre"`` for the real ATT&CK build and
``"mock"`` for the synthetic 15-actor fixture. Both are produced by the data
module and consumed identically by everything downstream, which is what lets the
engine and app be developed before the real ingestion is finished.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"
INTERIM_DIR: Path = DATA_DIR / "interim"
PROCESSED_DIR: Path = DATA_DIR / "processed"
MOCK_DIR: Path = DATA_DIR / "mock"

OUTPUTS_DIR: Path = PROJECT_ROOT / "outputs"
FIGURES_DIR: Path = OUTPUTS_DIR / "figures"
REPORTS_DIR: Path = OUTPUTS_DIR / "reports"

#: Raw ATT&CK Enterprise STIX bundle, as downloaded (data.stix_download).
ATTACK_BUNDLE_PATH: Path = RAW_DIR / "enterprise-attack.json"

#: Workspace names.
MITRE_DATASET = "mitre"
MOCK_DATASET = "mock"
KNOWN_DATASETS: tuple[str, ...] = (MITRE_DATASET, MOCK_DATASET)

#: What the UI and the evaluation module open when no dataset is specified.
#: Deliberately the mock set, so a fresh clone is usable before the real
#: ATT&CK build exists.
DEFAULT_DATASET = MOCK_DATASET


@dataclass(frozen=True)
class Workspace:
    """Resolves every artefact path for one dataset build.

    Example::

        ws = Workspace.get("mock")
        actors = storage.read_json(ws.actors)          # data module output
        weights = storage.read_dataframe(ws.weights)   # engine module output

    Attributes:
        name: Dataset name, e.g. ``"mitre"`` or ``"mock"``.
    """

    name: str = DEFAULT_DATASET

    # ------------------------------------------------------------------ ctor
    @classmethod
    def get(cls, name: str | None = None) -> "Workspace":
        """Return the workspace for ``name`` (defaults to :data:`DEFAULT_DATASET`).

        Unknown names are allowed on purpose -- a developer may want a private
        ``"scratch"`` build -- but they are not created implicitly; call
        :meth:`ensure` first.
        """
        return cls(name or DEFAULT_DATASET)

    # ----------------------------------------------------------- directories
    @property
    def root(self) -> Path:
        """Directory holding this dataset's processed artefacts."""
        return PROCESSED_DIR / self.name

    @property
    def figures_dir(self) -> Path:
        return FIGURES_DIR / self.name

    @property
    def reports_dir(self) -> Path:
        return REPORTS_DIR / self.name

    # ------------------------------------------- data module outputs (stage 1)
    @property
    def actors(self) -> Path:
        """``actors.json`` -- list of :class:`~ttp_similarity.schema.Actor` records."""
        return self.root / "actors.json"

    @property
    def actor_technique(self) -> Path:
        """``actor_technique.csv`` -- long/tidy actor-technique edge table."""
        return self.root / "actor_technique.csv"

    @property
    def techniques(self) -> Path:
        """``techniques.csv`` -- technique catalogue (id, name, tactics)."""
        return self.root / "techniques.csv"

    @property
    def technique_frequency(self) -> Path:
        """``technique_frequency.csv`` -- how many actors use each technique."""
        return self.root / "technique_frequency.csv"

    @property
    def data_manifest(self) -> Path:
        """``manifest.json`` -- provenance for the build (source, version, counts)."""
        return self.root / "manifest.json"

    # ---------------------------------------- engine module outputs (stage 2)
    @property
    def weights(self) -> Path:
        """``weights.csv`` -- per-technique discriminative weight."""
        return self.root / "weights.csv"

    @property
    def vector_space(self) -> Path:
        """``vector_space.npz`` -- weighted actor x technique matrix + labels."""
        return self.root / "vector_space.npz"

    @property
    def similarity(self) -> Path:
        """``similarity.npz`` -- actor x actor similarity matrix + labels."""
        return self.root / "similarity.npz"

    @property
    def clusters(self) -> Path:
        """``clusters.csv`` -- cluster assignment per actor."""
        return self.root / "clusters.csv"

    # ------------------------------------ evaluation module outputs (stage 3)
    @property
    def evaluation_report(self) -> Path:
        """``evaluation.json`` -- top-1 / top-3 retrieval accuracy report."""
        return self.reports_dir / "evaluation.json"

    @property
    def evaluation_trials(self) -> Path:
        """``evaluation_trials.csv`` -- one row per benchmark trial."""
        return self.reports_dir / "evaluation_trials.csv"

    # ------------------------------------------------------------- utilities
    def ensure(self) -> "Workspace":
        """Create the directories this workspace writes into. Idempotent."""
        for directory in (self.root, self.figures_dir, self.reports_dir):
            directory.mkdir(parents=True, exist_ok=True)
        return self

    def figure(self, filename: str) -> Path:
        """Path for a rendered figure inside this workspace."""
        return self.figures_dir / filename


def ensure_base_dirs() -> None:
    """Create the top-level data/output folders. Safe to call repeatedly."""
    for directory in (
        RAW_DIR,
        INTERIM_DIR,
        PROCESSED_DIR,
        MOCK_DIR,
        FIGURES_DIR,
        REPORTS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
