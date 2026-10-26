"""GUI E2E tests for range gate overlays on histogram and 2D plots."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtTest import QTest

from flowdesk_core.fcs_io import write_fcs_file
from flowdesk_core.models import GateSpec
from flowdesk_qt.channel_selector import COUNT_CHANNEL
from flowdesk_qt.main_window import MainWindow

pytestmark = [pytest.mark.gui, pytest.mark.gui_e2e]


def _wait_until(condition: Callable[[], bool]) -> None:
  for _ in range(400):
    if condition():
      return
    QTest.qWait(5)
  assert condition()


def _range_items(window: MainWindow) -> list[tuple[str, tuple[float, float]]]:
  return [
    (item.orientation, tuple(item.getRegion()))
    for item in window._plot_widget._gate_items
  ]


def test_range_gate_is_drawn_on_the_axis_showing_its_parameter(
  qapp, tmp_path: Path, gui_artifact_widgets: list[object]
) -> None:
  fcs_path = tmp_path / "range.fcs"
  values = np.arange(100.0)
  write_fcs_file(fcs_path, np.column_stack((values, values * 2.0)), ["FSC", "SSC"])

  window = MainWindow()
  gui_artifact_widgets.append(window)
  try:
    window.show()
    assert window._sample_browser.add_samples_from_paths([str(fcs_path)]) == 1
    sample = window._sample_browser.samples()[0]
    assert window._sample_browser.select_sample(sample.id)
    _wait_until(lambda: window._plot_widget._scatter is not None)

    fsc = window._channel_selector.x_channel_id()
    ssc = window._channel_selector.y_channel_id()
    window._gate_editor.add_gate(GateSpec(
      id="gate-fsc-range",
      name="FSC range",
      gate_type="range",
      x_parameter=fsc,
      thresholds={"min": 20.0, "max": 60.0},
    ))

    expected = {
      (fsc, COUNT_CHANNEL): [("vertical", (20.0, 60.0))],
      (fsc, ssc): [("vertical", (20.0, 60.0))],
      (ssc, fsc): [("horizontal", (20.0, 60.0))],
      (ssc, COUNT_CHANNEL): [],
    }
    for (x_id, y_id), items in expected.items():
      histogram = y_id == COUNT_CHANNEL
      window._channel_selector.set_selected_channels(x_id, y_id)
      _wait_until(
        lambda items=items, histogram=histogram: (
          window._plot_widget._is_histogram_mode is histogram
          and _range_items(window) == items
        )
      )
  finally:
    window.close()
