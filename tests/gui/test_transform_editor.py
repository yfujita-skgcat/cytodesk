"""GUI tests for versioned analysis transform editing and preview."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit  # noqa: E402

from flowdesk_core.models import ChannelSpec  # noqa: E402
from flowdesk_qt.transform_editor import TransformEditorDialog  # noqa: E402


def _app() -> QApplication:
  return QApplication.instance() or QApplication([])


def test_transform_editor_edits_logicle_parameters_and_round_trip_preview() -> None:
  app = _app()
  dialog = TransformEditorDialog(
    [],
    (ChannelSpec(id="signal", name="Signal"),),
    preview_values={"signal": np.array([-100.0, 0.0, 100.0, 262144.0])},
  )
  try:
    dialog.findChild(QLineEdit, "transformIdEdit").setText("logicle_signal")
    dialog.findChild(QLineEdit, "transformNameEdit").setText("Signal Logicle")
    dialog._parameter_combo.setCurrentIndex(0)
    dialog._type_combo.setCurrentText("logicle")
    dialog._setting_edits["T"].setText("262144")
    dialog._setting_edits["W"].setText("0.5")
    dialog._setting_edits["M"].setText("4.5")
    dialog._setting_edits["A"].setText("0")

    dialog._preview_current()

    preview = dialog.findChild(QLabel, "transformPreviewLabel").text()
    assert "inverse round-trip" in preview
    assert "4 finite events" in preview
    definitions = dialog.transforms()
    assert definitions[0]["transform_type"] == "logicle"
    assert definitions[0]["settings"]["T"] == 262144.0
    assert definitions[0]["settings"]["implementation_version"].startswith(
      "logicle-gml2"
    )
  finally:
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_transform_editor_exposes_complete_settings_for_each_new_type() -> None:
  app = _app()
  dialog = TransformEditorDialog(
    [], (ChannelSpec(id="signal", name="Signal"),)
  )
  try:
    expected = {
      "linear": {"scale", "offset"},
      "log": {"base", "invalid_value_policy"},
      "asinh": {"cofactor"},
      "logicle": {"T", "W", "M", "A", "implementation_version"},
    }
    for transform_type, setting_names in expected.items():
      dialog._type_combo.setCurrentText(transform_type)
      assert set(dialog._visible_setting_names()) == setting_names
  finally:
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_transform_editor_delete_preserves_neighbor_metadata() -> None:
  app = _app()
  referenced = {
    "id": "signal-log",
    "name": "Signal Log",
    "transform_type": "log",
    "parameter": "signal",
    "settings": {"base": 10.0, "invalid_value_policy": "to_nan"},
    "role": "analysis",
    "notes": "Created from the axis Transform selector.",
  }
  dialog = TransformEditorDialog(
    [
      {
        "id": "unused",
        "name": "Unused",
        "transform_type": "asinh",
        "parameter": "signal",
        "settings": {"cofactor": 1.0},
        "role": "analysis",
        "notes": "Unused definition",
      },
      referenced,
    ],
    (ChannelSpec(id="signal", name="Signal"),),
  )
  try:
    dialog._list.setCurrentRow(0)
    dialog._delete_transform()

    definitions = dialog.transforms()

    assert definitions == [referenced]
  finally:
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_transform_editor_allows_multiple_versions_and_noop_is_lossless() -> None:
  app = _app()
  definitions = [
    {
      "id": "signal-asinh",
      "name": "Signal Asinh",
      "transform_type": "asinh",
      "parameter": "signal",
      "settings": {"cofactor": 1.0},
      "role": "analysis",
      "notes": "Asinh version",
    },
    {
      "id": "signal-log",
      "name": "Signal Log",
      "transform_type": "log",
      "parameter": "signal",
      "settings": {"base": 10.0, "invalid_value_policy": "to_nan"},
      "role": "analysis",
      "notes": "Log version",
    },
  ]
  dialog = TransformEditorDialog(
    definitions,
    (ChannelSpec(id="signal", name="Signal"),),
  )
  try:
    assert dialog.transforms() == definitions
  finally:
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
