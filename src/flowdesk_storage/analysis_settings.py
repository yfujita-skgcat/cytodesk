"""Storage for sample-independent analysis settings bundles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flowdesk_core.analysis_settings import (
  ANALYSIS_SETTINGS_DOCUMENT_KIND,
  extract_analysis_settings,
  migrate_analysis_settings,
)
from flowdesk_storage.project import load_project
from flowdesk_storage.serialization import atomic_write_json, now_iso

ANALYSIS_SETTINGS_SUFFIX = ".flowdesk-settings"


def analysis_settings_bundle_path(path: str | Path) -> Path:
  """Append the settings-bundle suffix without replacing name components."""
  bundle = Path(path)
  if not bundle.name:
    raise ValueError("analysis settings bundle name must not be empty")
  if not bundle.name.lower().endswith(ANALYSIS_SETTINGS_SUFFIX):
    bundle = Path(f"{bundle}{ANALYSIS_SETTINGS_SUFFIX}")
  return bundle


def is_analysis_settings_bundle(path: str | Path) -> bool:
  """Return whether *path* is an existing settings bundle, not a project."""
  bundle = Path(path)
  manifest_path = bundle / "manifest.json"
  if not bundle.is_dir() or not manifest_path.is_file():
    return False
  try:
    with manifest_path.open(encoding="utf-8") as handle:
      data = json.load(handle)
  except (OSError, ValueError, TypeError):
    return False
  return data.get("document_kind") == ANALYSIS_SETTINGS_DOCUMENT_KIND


def save_analysis_settings(
  path: str | Path,
  project: dict[str, Any],
) -> None:
  """Write an atomic `.flowdesk-settings` directory bundle."""
  bundle = Path(path)
  if bundle.exists() and not is_analysis_settings_bundle(bundle):
    raise ValueError(
      f"refusing to overwrite a non-analysis-settings directory: {bundle}"
    )
  settings = extract_analysis_settings(
    project,
    source_project_id=str(project.get("project_id", "")) or None,
  )
  settings["created_at"] = now_iso()
  migrate_analysis_settings(settings)
  bundle.mkdir(parents=True, exist_ok=True)
  atomic_write_json(bundle / "manifest.json", settings)


def load_analysis_settings(path: str | Path) -> dict[str, Any]:
  """Load settings or extract settings from a normal `.flowdesk` project."""
  source = Path(path)
  manifest_path = source / "manifest.json"
  if not manifest_path.exists():
    raise ValueError(f"analysis settings manifest not found: {manifest_path}")
  with manifest_path.open(encoding="utf-8") as handle:
    data = json.load(handle)
  if data.get("document_kind") == ANALYSIS_SETTINGS_DOCUMENT_KIND:
    return migrate_analysis_settings(data)
  project = load_project(source)
  return extract_analysis_settings(
    project,
    source_project_id=str(project.get("project_id", "")) or None,
  )
