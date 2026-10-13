"""
The artifact store: how it is found, its marker, its layout and the artifacts inside it.
"""

import socket
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import __version__
from proj_helpers.paths import LOCAL_CONFIG, repo_root, resolve_path

ENV_VAR = "SUBICULUM_RNN_STORE"
MARKER = "store.yaml"
MANIFEST = "manifest.yaml"
STORE_VERSION = 1
KINDS = ("datasets", "models", "experiments")
CHOSEN_BY = {"flag": "--store", "env": f"${ENV_VAR}", "local": LOCAL_CONFIG,
             "argument": "the argument"}


class StoreError(Exception):
    pass


@dataclass(frozen=True)
class Artifact:
    id: str
    path: Path
    meta: dict


def _scan(directory: Path) -> tuple[list[Artifact], list[str]]:
    """
    Artifacts by id, plus the manifests that are malformed or declare the wrong id.
    """
    if not directory.is_dir():
        return [], []
    artifacts, broken = [], []
    for d in sorted(p for p in directory.iterdir() if p.is_dir()):
        manifest = d / MANIFEST
        if not manifest.is_file():
            continue
        meta = yaml.safe_load(manifest.read_text())
        if not isinstance(meta, dict):
            broken.append(f"{d.name}/{MANIFEST} is not a mapping")
        elif meta.get("id", d.name) != d.name:
            broken.append(f"{d.name}/{MANIFEST} declares id {meta['id']!r}")
        else:
            artifacts.append(Artifact(id=d.name, path=d, meta=meta))
    return artifacts, broken


@dataclass(frozen=True)
class Store:
    root: Path
    source: str  # flag, env, default, argument

    @property
    def marker(self) -> Path:
        return self.root / MARKER

    @property
    def initialized(self) -> bool:
        return self.marker.is_file()

    def kind_dir(self, kind: str) -> Path:
        return self.root / kind

    def read_marker(self) -> dict:
        if not self.initialized:
            raise StoreError(self._missing())
        try:
            marker = yaml.safe_load(self.marker.read_text()) or {}
        except OSError as e:
            raise StoreError(f"cannot read {self.marker}: {e.strerror}") from e
        version = marker.get("store_version")
        if not isinstance(version, int) or version > STORE_VERSION:
            raise StoreError(f"store at {self.root} has store_version {version!r}; "
                             f"this tool supports {STORE_VERSION}, update the tool")
        return marker

    def init(self) -> dict:
        if self.initialized:
            return self.read_marker()
        for kind in KINDS:
            self.kind_dir(kind).mkdir(parents=True, exist_ok=True)
        marker = {
            "store_version": STORE_VERSION,
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "hostname": socket.gethostname(),
            "tool_version": __version__,
        }
        self.marker.write_text(yaml.safe_dump(marker, sort_keys=False))
        return marker

    def _missing(self) -> str:
        if self.source == "default":
            return (f"no store at {self.root} (the default location; pass --store DIR, "
                    f"set {ENV_VAR}, or add STORE to {LOCAL_CONFIG}); "
                    f"run `store init` to create it")
        return (f"store not found at {self.root} (from {CHOSEN_BY[self.source]}); "
                f"is the drive mounted? run `store init`")

    def artifacts(self, kind: str) -> list[Artifact]:
        artifacts, broken = _scan(self.kind_dir(kind))
        if broken:
            raise StoreError(f"{self.kind_dir(kind)}: " + "; ".join(broken))
        return artifacts

    def counts(self) -> dict[str, int]:
        return {kind: len(_scan(self.kind_dir(kind))[0]) for kind in KINDS}


def resolve_store(flag: str | None, env: Mapping[str, str] | None = None,
                  local_file: Path | None = None) -> Store:
    root, source = resolve_path(flag, env_var=ENV_VAR, key="STORE",
                                default=repo_root() / "artifacts", env=env,
                                local_file=local_file)
    return Store(root, source)


def open_store(flag: str | None, env: Mapping[str, str] | None = None,
               local_file: Path | None = None) -> Store:
    store = resolve_store(flag, env, local_file)
    store.read_marker()
    return store
