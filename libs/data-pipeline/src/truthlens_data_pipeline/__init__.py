from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .acquisition import AcquiredItem, acquire_discovered_items
    from .discovery import PublicSourceSpec, DiscoveredItem, build_discovery_run, persist_discovery_run
    from .labeling import prepare_label_batches
    from .manifests import DiscoveryRunManifest, SourceManifestRecord, build_source_manifest
    from .normalization import normalize_acquired_items
    from .paths import read_json, read_jsonl, repo_root, write_json, write_jsonl

_EXPORTS = {
    "AcquiredItem": (".acquisition", "AcquiredItem"),
    "DiscoveredItem": (".discovery", "DiscoveredItem"),
    "DiscoveryRunManifest": (".manifests", "DiscoveryRunManifest"),
    "PublicSourceSpec": (".discovery", "PublicSourceSpec"),
    "SourceManifestRecord": (".manifests", "SourceManifestRecord"),
    "acquire_discovered_items": (".acquisition", "acquire_discovered_items"),
    "build_discovery_run": (".discovery", "build_discovery_run"),
    "build_source_manifest": (".manifests", "build_source_manifest"),
    "normalize_acquired_items": (".normalization", "normalize_acquired_items"),
    "persist_discovery_run": (".discovery", "persist_discovery_run"),
    "prepare_label_batches": (".labeling", "prepare_label_batches"),
    "read_json": (".paths", "read_json"),
    "read_jsonl": (".paths", "read_jsonl"),
    "repo_root": (".paths", "repo_root"),
    "write_json": (".paths", "write_json"),
    "write_jsonl": (".paths", "write_jsonl"),
}

__all__ = [
    "AcquiredItem",
    "DiscoveredItem",
    "DiscoveryRunManifest",
    "PublicSourceSpec",
    "SourceManifestRecord",
    "acquire_discovered_items",
    "build_discovery_run",
    "build_source_manifest",
    "normalize_acquired_items",
    "persist_discovery_run",
    "prepare_label_batches",
    "read_json",
    "read_jsonl",
    "repo_root",
    "write_json",
    "write_jsonl",
]


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
