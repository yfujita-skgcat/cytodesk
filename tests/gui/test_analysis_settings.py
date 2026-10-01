"""GUI integration checks for analysis settings actions and application."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from flowdesk_core.analysis_settings import extract_analysis_settings
from flowdesk_core.project_commands import (
  ReplaceAnalysisSettingsCommand,
  UndoStack,
)
from flowdesk_qt.main_window import MainWindow

pytestmark = pytest.mark.gui


def _settings() -> dict[str, object]:
  return extract_analysis_settings({
    "project_id": "source",
    "gating_strategies_data": {
      "default_strategy": {
        "id": "default_strategy",
        "name": "Imported",
        "root_population_id": "all_events",
        "gates": [],
      }
    },
    "derived_parameters": [],
    "transforms": [],
    "compensation_matrices": [],
    "statistics": [],
    "auto_gate_templates": [],
    "magnetic_gate_templates": [],
    "tethered_gate_templates": [],
    "plot_views": [],
  })


def test_analysis_settings_actions_have_stable_names_and_apply(qapp) -> None:
  window = MainWindow()
  try:
    assert window.action_save_analysis_settings.objectName() == (
      "actionSaveAnalysisSettings"
    )
    assert window.action_load_analysis_settings.objectName() == (
      "actionLoadAnalysisSettings"
    )
    assert window.action_undo_analysis_settings.objectName() == (
      "actionUndoAnalysisSettings"
    )
    assert window.action_redo_analysis_settings.objectName() == (
      "actionRedoAnalysisSettings"
    )
    assert window.action_pipeline_execution_settings.objectName() == (
      "actionPipelineExecutionSettings"
    )
    window._analysis_settings_undo_stack = UndoStack(
      window._build_project_manifest(),
      on_changed=window._on_analysis_settings_state_changed,
    )
    window._analysis_settings_undo_stack.execute(
      ReplaceAnalysisSettingsCommand(_settings())
    )
    assert window._results_stale
    assert window.action_undo_analysis_settings.isEnabled()
    window._on_undo_analysis_settings()
    assert window.action_redo_analysis_settings.isEnabled()
  finally:
    window.close()
    window.deleteLater()


def test_save_analysis_settings_uses_literal_suffix_and_parent_history(
  qapp, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
  window = MainWindow()
  settings = QSettings()
  key = window._FILE_DIALOG_DIRECTORY_KEYS["save_analysis_settings"]
  previous = settings.value(key, None)
  saved: list[Path] = []
  try:
    settings.remove(key)
    monkeypatch.setattr(
      "flowdesk_qt.main_window.QFileDialog.getSaveFileName",
      lambda *_args, **_kwargs: (str(tmp_path / "exp1.v2"), ""),
    )
    monkeypatch.setattr(
      "flowdesk_qt.main_window.save_analysis_settings",
      lambda path, _project: saved.append(Path(path)),
    )
    monkeypatch.setattr(window, "_build_project_manifest", lambda: {})

    window._on_save_analysis_settings()

    assert saved == [tmp_path / "exp1.v2.flowdesk-settings"]
    assert window._file_dialog_directory("save_analysis_settings") == str(
      tmp_path.resolve()
    )
  finally:
    if previous is None:
      settings.remove(key)
    else:
      settings.setValue(key, previous)
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_save_analysis_settings_cancel_does_not_update_history(
  qapp, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
  window = MainWindow()
  settings = QSettings()
  key = window._FILE_DIALOG_DIRECTORY_KEYS["save_analysis_settings"]
  previous = settings.value(key, None)
  try:
    settings.remove(key)
    monkeypatch.setattr(
      "flowdesk_qt.main_window.QFileDialog.getSaveFileName",
      lambda *_args, **_kwargs: ("", ""),
    )

    window._on_save_analysis_settings()

    assert settings.value(key, None) is None
  finally:
    if previous is None:
      settings.remove(key)
    else:
      settings.setValue(key, previous)
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_save_analysis_settings_rejects_existing_non_bundle_directory(
  qapp, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
  window = MainWindow()
  target = tmp_path / "existing.flowdesk-settings"
  target.mkdir()
  warnings: list[str] = []
  monkeypatch.setattr(
    "flowdesk_qt.main_window.QFileDialog.getSaveFileName",
    lambda *_args, **_kwargs: (str(tmp_path / "existing"), ""),
  )
  monkeypatch.setattr(
    "flowdesk_qt.main_window.QMessageBox.warning",
    lambda _parent, _title, message: warnings.append(message),
  )
  try:
    window._on_save_analysis_settings()
    assert warnings
    assert "not an analysis settings bundle" in warnings[0]
  finally:
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_save_analysis_settings_confirms_existing_bundle(
  qapp, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
  window = MainWindow()
  target = tmp_path / "existing.flowdesk-settings"
  target.mkdir()
  (target / "manifest.json").write_text(
    '{"document_kind": "analysis_settings"}', encoding="utf-8"
  )
  saved: list[Path] = []
  questions: list[str] = []
  monkeypatch.setattr(
    "flowdesk_qt.main_window.QFileDialog.getSaveFileName",
    lambda *_args, **_kwargs: (str(tmp_path / "existing"), ""),
  )
  monkeypatch.setattr(
    "flowdesk_qt.main_window.QMessageBox.question",
    lambda _parent, _title, message, *_args: (
      questions.append(message) or QMessageBox.StandardButton.Yes
    ),
  )
  monkeypatch.setattr(
    "flowdesk_qt.main_window.save_analysis_settings",
    lambda path, _project: saved.append(Path(path)),
  )
  monkeypatch.setattr(window, "_build_project_manifest", lambda: {})
  try:
    window._on_save_analysis_settings()
    assert saved == [target]
    assert questions and str(target) in questions[0]
  finally:
    window.close()
    window.deleteLater()
    qapp.processEvents()
