"""Tests for range gate display, drag editing, and plot-based creation."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PySide6 = pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
shiboken6 = pytest.importorskip("shiboken6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from flowdesk_core.gating_strategy import (  # noqa: E402
  evaluate_gating_strategy_with_membership,
)
from flowdesk_core.models import GateSpec, GatingStrategySpec, TransformSpec  # noqa: E402
from flowdesk_qt.main_window import MainWindow  # noqa: E402
from flowdesk_qt.plot_widget import (  # noqa: E402
  PlotWidget,
  _RangeGateLine,
  _RangeGateRegion,
)


def _app() -> QApplication:
  app = QApplication.instance()
  if app is None:
    app = QApplication([])
  return app


def _flush_deferred_delete(item: object) -> None:
  QCoreApplication.sendPostedEvents(item, QEvent.Type.DeferredDelete)


def _range_gate(**thresholds: float) -> GateSpec:
  return GateSpec(
    id="gate-range",
    name="range",
    gate_type="range",
    x_parameter="X",
    thresholds=dict(thresholds),
  )


def _pen_state(item: object) -> tuple[str, float, object]:
  pen = item.pen() if callable(item.pen) else item.pen
  return (pen.color().name(), pen.widthF(), pen.style())


def test_two_sided_range_gate_is_vertical_band_on_x_axis() -> None:
  app = _app()
  widget = PlotWidget()
  try:
    widget.add_gate_overlay(_range_gate(min=2.0, max=8.0), gate_index=0)

    assert len(widget._gate_items) == 1
    item = widget._gate_items[0]
    assert isinstance(item, _RangeGateRegion)
    assert item.orientation == "vertical"
    assert item.getRegion() == pytest.approx((2.0, 8.0))
    assert widget.display_state()["hidden_gate_reasons"] == []
  finally:
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_range_gate_on_y_axis_is_horizontal_band() -> None:
  app = _app()
  widget = PlotWidget()
  try:
    widget.add_gate_overlay(_range_gate(min=2.0, max=8.0), gate_index=0, range_axis="y")

    item = widget._gate_items[0]
    assert isinstance(item, _RangeGateRegion)
    assert item.orientation == "horizontal"
  finally:
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_range_gate_drag_edit_round_trips_sorted_thresholds() -> None:
  app = _app()
  widget = PlotWidget()
  edits: list[tuple[int, GateSpec]] = []
  try:
    gate = _range_gate(min=2.0, max=8.0)
    widget.on_gate_geometry_changed(lambda index, edited: edits.append((index, edited)))
    widget.add_gate_overlay(gate, gate_index=3)
    item = widget._gate_items[0]

    # Dragging one edge past the other must still store min <= max.
    # setRegion emits sigRegionChangeFinished like a finished edge drag.
    item.setRegion((9.0, 4.0))

    assert len(edits) == 1
    index, edited = edits[0]
    assert index == 3
    assert edited.id == gate.id
    assert edited.y_parameter is None
    assert edited.thresholds == pytest.approx({"min": 4.0, "max": 9.0})
  finally:
    widget.close()
    widget.deleteLater()
    app.processEvents()


@pytest.mark.parametrize("bound", ["min", "max"])
def test_one_sided_range_gate_stays_one_sided_after_edit(bound: str) -> None:
  app = _app()
  widget = PlotWidget()
  edits: list[GateSpec] = []
  try:
    gate = _range_gate(**{bound: 5.0})
    widget.on_gate_geometry_changed(lambda _index, edited: edits.append(edited))
    widget.add_gate_overlay(gate, gate_index=0)
    item = widget._gate_items[0]
    assert isinstance(item, _RangeGateLine)
    assert item.angle == 90

    item.setValue(7.5)
    item.sigPositionChangeFinished.emit(item)

    assert [edited.thresholds for edited in edits] == [{bound: 7.5}]
  finally:
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_unbounded_range_gate_has_no_overlay() -> None:
  app = _app()
  widget = PlotWidget()
  try:
    widget.add_gate_overlay(_range_gate(), gate_index=0)
    assert widget._gate_items == []
    assert widget.display_state()["hidden_gate_reasons"] == []
  finally:
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_range_gate_transform_must_match_drawn_axis() -> None:
  app = _app()
  widget = PlotWidget()
  transform = TransformSpec(
    id="asinh_y",
    name="asinh Y",
    transform_type="asinh",
    parameter="Y",
    settings={"cofactor": 150.0},
  )
  gate = GateSpec(
    id="gate-range-t",
    name="range t",
    gate_type="range",
    x_parameter="Y",
    x_transform_id=transform.id,
    thresholds={"min": 0.5, "max": 2.0},
  )
  try:
    # The gate's coordinates are asinh_y; the X axis is linear.
    widget.set_axis_transform_specs(None, transform)
    widget.add_gate_overlay(gate, gate_index=0, range_axis="x")
    assert widget._gate_items == []
    assert len(widget.display_state()["hidden_gate_reasons"]) == 1

    widget.clear_gates()
    widget.add_gate_overlay(gate, gate_index=0, range_axis="y")
    assert len(widget._gate_items) == 1
    assert widget._gate_items[0].orientation == "horizontal"
  finally:
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_range_gate_highlight_and_style_update_edge_pens() -> None:
  app = _app()
  widget = PlotWidget()
  try:
    widget.add_gate_overlay(_range_gate(min=2.0, max=8.0), gate_index=0)
    item = widget._gate_items[0]

    widget.highlight_gate_id("gate-range")
    assert all(line.pen.widthF() == 3 for line in item.lines)
    assert item.pen().color().name() == widget._contrast_gate_color()

    widget.highlight_gate_id(None)
    assert item.pen().color().name() == widget._style.gate_outline_color.lower()
  finally:
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_range_gate_export_restores_editing_pens(tmp_path) -> None:
  app = _app()
  widget = PlotWidget()
  try:
    widget.resize(320, 240)
    widget.plot_events(np.array([1.0, 5.0, 9.0]), np.array([1.0, 2.0, 3.0]))
    widget.add_gate_overlay(_range_gate(min=2.0, max=8.0), gate_index=0)
    widget.add_gate_overlay(_range_gate(max=6.0), gate_index=1)
    before = [_pen_state(item) for item in widget._gate_items]

    path = tmp_path / "range.png"
    widget.export_png(path, width=320, height=240)

    assert path.stat().st_size > 0
    assert [_pen_state(item) for item in widget._gate_items] == before
  finally:
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_range_gate_does_not_drive_auto_range() -> None:
  app = _app()
  widget = PlotWidget()
  try:
    widget.add_gate_overlay(_range_gate(min=-1.0e9, max=1.0e9), gate_index=0)
    vb = widget._view_box()
    assert vb is not None
    assert vb.childrenBounds() == [None, None]
  finally:
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_clear_gates_disconnects_and_disposes_range_items() -> None:
  app = _app()
  widget = PlotWidget()
  try:
    for gate in (_range_gate(min=1.0, max=3.0), _range_gate(max=3.0)):
      widget.add_gate_overlay(gate, gate_index=0)
      item = widget._gate_items[0]

      widget.clear_gates()
      _flush_deferred_delete(item)

      assert widget._gate_items == []
      assert widget._gate_item_callbacks == {}
      assert shiboken6.isValid(item) is False
  finally:
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_main_window_range_edit_updates_gate_and_counts() -> None:
  app = _app()
  window = MainWindow()
  events = np.array([[1.0], [3.0], [5.0], [7.0], [9.0]])
  try:
    gate = _range_gate(min=2.0, max=8.0)
    window._gate_editor.add_gate(gate)
    edited = GateSpec(
      id=gate.id,
      name=gate.name,
      gate_type="range",
      x_parameter="X",
      thresholds={"min": 4.0, "max": 10.0},
    )
    window._queue_gate_geometry_changed(0, edited)
    window._flush_pending_gate_geometry_updates()

    stored = window._gate_editor.gates()[0]
    assert stored.thresholds == {"min": 4.0, "max": 10.0}
    _results, masks = evaluate_gating_strategy_with_membership(
      GatingStrategySpec(id="s", name="s", gates=(stored,)),
      events,
      ["X"],
    )
    assert masks[gate.id].tolist() == [False, False, True, True, True]
  finally:
    window.close()
    window.deleteLater()
    app.processEvents()
