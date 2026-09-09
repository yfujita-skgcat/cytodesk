from __future__ import annotations

import json
import shutil
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from flowdesk_cli.batch_plot import _write_render_payload
from flowdesk_core.models import BatchPlotExportSpec
from flowdesk_core.plot_export import prepare_display_export, write_plot_png
from flowdesk_core.plot_presentation import OverlaySourceResolution
from flowdesk_core.plot_scene import PlotScene, resolve_plot_layout
from flowdesk_qt.main_window import MainWindow
from flowdesk_qt.plot_widget import PlotWidget
from flowdesk_qt.qt_plot_export import render_batch_plot_qt

pytestmark = pytest.mark.gui


def test_live_export_metadata_includes_manual_overlay_layers(qapp, monkeypatch) -> None:
  window = MainWindow()
  try:
    window._current_sample_id = "s1"
    window._plot_views = [{
      "id": "main-view", "plot_type": "scatter",
      "x_parameter": "x", "y_parameter": "y",
      "presentation": {}, "display_scene": {},
    }]
    window._sample_browser._manual_overlay_sample_ids = {"s2", "s3"}
    monkeypatch.setattr(
      window._plot_widget, "export_data_layers", lambda: {
        "layers": [
          (np.array([1.0]), np.array([1.0]), {}),
          (np.array([2.0]), np.array([2.0]), {"source_id": "manual:s3"}),
          (np.array([3.0]), np.array([3.0]), {"source_id": "manual:s2"}),
        ],
        "event_colors": None,
      },
    )
    metadata = window._current_plot_export_metadata()
    assert metadata["ordered_source_ids"] == ["s1", "manual:s3", "manual:s2"]
    assert metadata["source_draw_order"] == ["s1", "manual:s3", "manual:s2"]
  finally:
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_current_view_export_calls_typed_prepared_dispatcher(qapp, monkeypatch) -> None:
  """The user-facing current-view path must not call the raw Qt wrapper."""
  window = MainWindow()
  captured: dict[str, object] = {}
  try:
    window._current_sample_id = "s1"
    monkeypatch.setattr(
      window._plot_widget, "export_data_layers", lambda: {
        "layers": [
          (np.array([0.25, 0.75]), np.array([0.25, 0.75]), {}),
        ],
        "event_colors": None,
      },
    )
    monkeypatch.setattr(window._plot_widget, "view_range", lambda: ((0.0, 1.0), (0.0, 1.0)))
    monkeypatch.setattr(
      window._sample_browser, "overlay_state", lambda: {"manual_overlay_colors": {}},
    )

    def capture(path, **kwargs):
      captured["path"] = path
      captured.update(kwargs)

    monkeypatch.setattr("flowdesk_qt.main_window.render_prepared_plot_qt", capture)
    metadata = {
      "plot_id": "main-view", "plot_type": "scatter",
      "ordered_source_ids": ["s1"], "source_draw_order": ["s1"],
      "sources": [{
        "source_id": "s1", "sample_id": "s1", "population_id": "all_events",
        "display_name": "Sample", "visible": True,
      }],
      "presentation": {"single_color": "#3366cc"},
      "scene": {
        "x_parameter": "x", "y_parameter": "y", "view_range": [[0.0, 1.0], [0.0, 1.0]],
        "title_lines": ["Sample"], "title_colors": ["#3366cc"], "gates": [],
      },
    }
    request = SimpleNamespace(
      format_name="PNG", width=300, height=200, dpi=96,
      raster_resolution_mode="legacy_pixel_dimensions", aspect_1_to_1=False,
      include_title=True, include_axis_labels=True, include_ticks=True,
      include_gates=True, include_legend=True, include_status_banner=False,
    )
    window._export_current_plot_core("plot.png", request, metadata)
    assert captured["path"] == "plot.png"
    prepared = captured["prepared"]
    assert prepared.source_order == ("s1",)
    assert captured["layers"] == {"s1": ((0.25, 0.75), (0.25, 0.75))}
  finally:
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_plot_scene_sanitizes_nonfinite_layout_metadata() -> None:
  scene = PlotScene.from_mapping({
    "plot_area": [float("nan"), 50.0, 20.0, 60.0],
    "title_baseline_y": float("nan"),
    "layout_title_line_count": float("nan"),
  })
  assert scene.plot_area == (60.0, 50.0, 20.0, 60.0)
  assert scene.title_baseline_y is None
  assert scene.layout_title_line_count is None


def test_shared_display_export_payload_resolves_overlay_titles_and_colors() -> None:
  prepared = prepare_display_export(
    "main-view", "scatter",
    (
      {"source_id": "s1", "display_name": "Blue", "visible": True, "order": 0},
      {"source_id": "s2", "display_name": "Red", "visible": True, "order": 1},
      {"source_id": "s3", "display_name": "Green", "visible": True, "order": 2},
    ),
    tuple(OverlaySourceResolution(source_id, "compatible", index) for index, source_id in
          enumerate(("s1", "s2", "s3"))),
    presentation={
      "title_mode": "overlay_sample_titles", "single_color": "#0000ff",
      "x_axis_display_label": "iRFP670 (APC-A)",
      "y_axis_display_label": "EGFP (FITC-A)",
    },
    active_source_id="s1", manual_overlay_colors={"s2": "#ff0000", "s3": "#00ff00"},
    scene={"x_axis_label": "iRFP670 (APC-A)", "y_axis_label": "EGFP (FITC-A)"},
  )
  assert prepared.scene.title_lines == ("Blue", "Red", "Green")
  assert prepared.scene.title_colors == ("#0000ff", "#ff0000", "#00ff00")
  assert prepared.scene.x_axis_label == "iRFP670 (APC-A)"
  assert prepared.scene.y_axis_label == "EGFP (FITC-A)"
  assert prepared.resolved_presentation.presentation.x_axis_display_label == "iRFP670 (APC-A)"


def test_qt_current_view_adapter_matches_shared_png_writer(qapp, tmp_path) -> None:
  prepared = prepare_display_export(
    "main-view", "scatter",
    ({"source_id": "s1", "display_name": "Sample", "visible": True, "order": 0},),
    (OverlaySourceResolution("s1", "compatible", 0),),
    presentation={"single_color": "#3366cc", "x_axis_display_label": "X"},
    active_source_id="s1",
  )
  options = BatchPlotExportSpec(id="parity", name="Parity", width=300, height=200)
  adapter_path = tmp_path / "adapter.png"
  core_path = tmp_path / "core.png"
  render_batch_plot_qt(
    adapter_path,
    raw_layers={"s1": (np.array([1.0, 10.0]), np.array([2.0, 20.0]))},
    source_ids=("s1",), source_styles={}, presentation={}, x_parameter="x",
    y_parameter="y", title_lines=(), title_colors=(), x_transform=None,
    y_transform=None, x_range=(1.0, 10.0), y_range=(2.0, 20.0), gates=(),
    width=300, height=200, options=options, prepared=prepared,
  )
  write_plot_png(
    core_path, prepared, layers={"s1": ((0.0, 1.0), (0.0, 1.0))},
    options=options, width=300, height=200,
  )
  assert adapter_path.read_bytes() == core_path.read_bytes()


def test_qt_export_skips_nonfinite_display_events(qapp, tmp_path) -> None:
  path = tmp_path / "finite.png"
  render_batch_plot_qt(
    path,
    raw_layers={"s1": (np.array([1.0, np.nan, 10.0]), np.array([2.0, 3.0, 20.0]))},
    source_ids=("s1",),
    source_styles={"s1": {"color": "#000000", "marker_size": 1.5}},
    presentation={"background_color": "#ffffff"},
    x_parameter="x", y_parameter="y", title_lines=("Sample",),
    title_colors=("#000000",), x_transform=None, y_transform=None,
    x_range=(1.0, 10.0), y_range=(2.0, 20.0), gates=(), width=300, height=200,
    options=BatchPlotExportSpec(id="finite", name="Finite"),
    export_metadata={"test": True},
  )
  metadata = json.loads(path.with_suffix(".png.json").read_text(encoding="utf-8"))
  assert metadata["display_state"]["input_event_count"] == 3
  assert metadata["display_state"]["displayed_event_count"] == 2


def test_qt_batch_renderer_writes_the_shared_scene_and_image(qapp, tmp_path) -> None:
  path = tmp_path / "plot.png"
  render_batch_plot_qt(
    path,
    raw_layers={"s1": (np.array([1.0, 10.0]), np.array([2.0, 20.0]))},
    source_ids=("s1",),
    source_styles={"s1": {"color": "#000000", "alpha": 0.6, "marker_size": 1.5}},
    presentation={
      "background_color": "#ffffff", "x_axis_display_label": "X",
      "y_axis_display_label": "Y", "show_grid": True,
    },
    x_parameter="x", y_parameter="y",
    title_lines=("Sample 1",), title_colors=("#4c78a8",),
    x_transform=None, y_transform=None,
    x_range=(1.0, 10.0), y_range=(2.0, 20.0), gates=(),
    width=400, height=300,
    options=BatchPlotExportSpec(
      id="export", name="Export", include_title=True,
      include_axis_labels=True, include_ticks=True,
    ),
    export_metadata={"test_marker": True},
  )
  assert path.exists() and path.stat().st_size > 1_000
  metadata = json.loads(path.with_suffix(".png.json").read_text(encoding="utf-8"))
  assert metadata["test_marker"] is True
  assert metadata["scene_hash"] == PlotScene.from_mapping(
    metadata["scene"]
  ).scene_hash()
  assert metadata["display_state"]["displayed_event_count"] == 2


def test_live_gui_and_core_export_resolve_the_same_layout(qapp, tmp_path) -> None:
  widget = PlotWidget()
  try:
    widget.resize(400, 300)
    widget.show()
    widget.plot_events(
      np.array([1.0, 10.0, 5.0]), np.array([2.0, 20.0, 8.0]),
      x_label="X", y_label="Y",
    )
    widget.set_manual_view_range((1.0, 10.0), (2.0, 20.0))
    widget.set_presentation({
      "title": "Line one\nLine two", "x_axis_display_label": "X",
      "y_axis_display_label": "Y",
    })
    qapp.processEvents()
    gui_path = tmp_path / "gui.png"
    assert widget.grab().save(str(gui_path))
    width, height = widget.canvas_size()
    margins = widget.plot_area_margins()
    assert widget.scene_ticks()["x_ticks"]
    assert widget.scene_ticks()["y_ticks"]
    scene = PlotScene.from_mapping({
      "plot_area": margins, "title_lines": ["Line one", "Line two"],
      "title_colors": ["#000000", "#000000"],
      "x_axis_label": "X", "y_axis_label": "Y", "source_order": ["s1"],
    })
    gui_layout = resolve_plot_layout(
      scene, {"title_font": {"size": 14}, "tick_font": {"size": 10},
              "axis_label_font": {"size": 14}}, width=width, height=height,
    ).to_mapping()
  finally:
    widget.close()
    widget.deleteLater()
  path = tmp_path / "core.png"
  render_batch_plot_qt(
    path,
    raw_layers={"s1": (np.array([1.0, 10.0, 5.0]), np.array([2.0, 20.0, 8.0]))},
    source_ids=("s1",), source_styles={"s1": {"color": "#000000", "alpha": 0.6}},
    presentation={"background_color": "#ffffff", "x_axis_display_label": "X",
                  "y_axis_display_label": "Y"},
    x_parameter="x", y_parameter="y", title_lines=("Line one", "Line two"),
    title_colors=("#000000", "#000000"), x_transform=None, y_transform=None,
    x_range=(1.0, 10.0), y_range=(2.0, 20.0), gates=(), width=width, height=height,
    options=BatchPlotExportSpec(
      id="layout", name="Layout", width=width, height=height,
      include_title=True, include_axis_labels=True, include_ticks=True,
    ),
    plot_area=margins,
  )
  export_layout = json.loads(
    path.with_suffix(path.suffix + ".json").read_text()
  )["plot_layout"]
  assert export_layout["plot_rect"] == gui_layout["plot_rect"]
  assert export_layout["title_baselines"] == gui_layout["title_baselines"]
  with Image.open(gui_path) as gui_image, Image.open(path) as export_image:
    gui_pixels = np.asarray(gui_image.convert("RGB"), dtype=np.float64)
    export_pixels = np.asarray(export_image.convert("RGB"), dtype=np.float64)
  normalized_rmse = float(
    np.sqrt(np.mean(np.square(gui_pixels - export_pixels))) / 255.0
  )
  assert normalized_rmse < 0.22


def test_gui_snapshot_matches_dpi_scaled_batch_at_logical_size(qapp, tmp_path) -> None:
  """Compare the real batch writer at 300 DPI in the GUI's logical canvas.

  A DPI-scaled PNG intentionally has more raster pixels than the on-screen
  canvas.  Comparing it at the image-viewer's fit-to-window zoom makes dots and
  fonts appear smaller.  The scientific/display contract is the logical
  canvas, so the batch image is downsampled to that canvas before comparison.
  """
  widget = PlotWidget()
  try:
    widget.resize(400, 300)
    widget.show()
    x_values = np.linspace(1.0, 10.0, 120)
    y_values = 2.0 + x_values * 1.7
    widget.plot_events(x_values, y_values, x_label="APC-A", y_label="FITC-A")
    widget.set_manual_view_range((1.0, 10.0), (2.0, 20.0))
    widget.set_presentation({
      "title_mode": "current_sample", "title": "Parity sample",
      "x_axis_display_label": "APC-A", "y_axis_display_label": "FITC-A",
    })
    qapp.processEvents()
    gui_path = tmp_path / "gui-logical.png"
    assert widget._glw.grab().save(str(gui_path))
    width, height = widget.canvas_size()
    margins = widget.plot_area_margins()
    ticks = widget.scene_ticks()
    axis_anchors = widget.axis_label_anchors()
    scene = PlotScene.from_mapping({
      "plot_area": margins,
      "view_range": [[1.0, 10.0], [2.0, 20.0]],
      "x_ticks": ticks.get("x_ticks", []), "y_ticks": ticks.get("y_ticks", []),
      "title_lines": ["Parity sample"],
      "title_colors": ["#000000"],
      "x_axis_label": "APC-A", "y_axis_label": "FITC-A",
      "y_axis_label_anchor": axis_anchors.get("y_axis_label_anchor"),
      "axis_label_canvas_size": [width, height],
      "source_order": ["s1"], "source_draw_order": ["s1"],
    })
    prepared = prepare_display_export(
      "main-view", "scatter",
      ({"source_id": "s1", "display_name": "Parity sample", "visible": True,
        "order": 0},),
      (OverlaySourceResolution("s1", "compatible", 0),),
      presentation={
        "title_mode": "current_sample", "title": "Parity sample",
        "single_color": "#000000", "x_axis_display_label": "APC-A",
        "y_axis_display_label": "FITC-A",
      },
      active_source_id="s1", scene=scene.to_mapping(),
    )
  finally:
    widget.close()
    widget.deleteLater()

  batch_path = tmp_path / "batch-300dpi.png"
  options = BatchPlotExportSpec(
    id="batch-parity", name="Batch parity", width=width, height=height,
    dpi=300, raster_resolution_mode="dpi_scaled", include_title=True,
    include_axis_labels=True, include_ticks=True,
  )
  _write_render_payload(
    batch_path, prepared,
    {"s1": (tuple(((x_values - 1.0) / 9.0).tolist()),
             tuple(((y_values - 2.0) / 18.0).tolist()))},
    {}, options,
  )
  with Image.open(gui_path) as gui_image, Image.open(batch_path) as batch_image:
    assert batch_image.size == (round(width * 300 / 96), round(height * 300 / 96))
    normalized_batch = batch_image.convert("RGB").resize(
      gui_image.size, Image.Resampling.LANCZOS,
    )
    gui_pixels = np.asarray(gui_image.convert("RGB"), dtype=np.float64)
    batch_pixels = np.asarray(normalized_batch, dtype=np.float64)
  normalized_rmse = float(
    np.sqrt(np.mean(np.square(gui_pixels - batch_pixels))) / 255.0
  )
  assert normalized_rmse < 0.22
  metadata = json.loads(batch_path.with_suffix(".png.json").read_text())
  assert metadata["export_canvas"]["logical_width"] == width
  assert metadata["export_canvas"]["logical_height"] == height
  assert metadata["export_canvas"]["raster_width"] == round(width * 300 / 96)
  assert metadata["plot_layout"]["y_axis_label_anchor"] == [
    pytest.approx(axis_anchors["y_axis_label_anchor"][0]),
    pytest.approx(axis_anchors["y_axis_label_anchor"][1]),
  ]


def test_current_view_export_preserves_gui_marker_size_and_color(qapp, tmp_path) -> None:
  """The shared export payload must retain the live Qt point presentation."""
  widget = PlotWidget()
  try:
    widget.resize(400, 300)
    widget.show()
    x_value, y_value = 0.37, 0.63
    widget.plot_events(
      np.array([x_value]), np.array([y_value]), x_label="X", y_label="Y",
    )
    widget.set_manual_view_range((0.0, 1.0), (0.0, 1.0))
    widget.set_presentation({
      "single_color": "#ff0000", "single_dot_size": 4.0,
      "show_grid": False, "title": "",
      "x_axis_display_label": "", "y_axis_display_label": "",
    })
    qapp.processEvents()
    gui_path = tmp_path / "gui-dot.png"
    assert widget._glw.grab().save(str(gui_path))
    width, height = widget.canvas_size()
    margins = widget.plot_area_margins()
    scene = PlotScene.from_mapping({
      "plot_area": margins,
      "view_range": [[0.0, 1.0], [0.0, 1.0]],
      "title_lines": [], "x_axis_label": "", "y_axis_label": "",
      "source_order": ["s1"], "source_draw_order": ["s1"],
    })
    prepared = prepare_display_export(
      "dot-view", "scatter",
      ({"source_id": "s1", "display_name": "S", "visible": True, "order": 0},),
      (OverlaySourceResolution("s1", "compatible", 0),),
      presentation={
        "single_color": "#ff0000", "single_dot_size": 4.0,
        "background_color": "#ffffff", "show_grid": False,
      },
      active_source_id="s1", scene=scene.to_mapping(),
    )
    style = prepared.resolved_presentation.presentation.source_styles[0]
    assert style.marker_size == pytest.approx(4.0)
    assert style.color == "#ff0000"
    assert style.alpha == pytest.approx(0.60)
    overlay_prepared = prepare_display_export(
      "dot-overlay", "scatter",
      (
        {"source_id": "s1", "display_name": "S", "visible": True, "order": 0},
        {"source_id": "s2", "display_name": "Overlay", "visible": True, "order": 1},
      ),
      (
        OverlaySourceResolution("s1", "compatible", 0),
        OverlaySourceResolution("s2", "compatible", 1),
      ),
      presentation={
        "single_color": "#ff0000", "single_dot_size": 4.0,
        "source_styles": [{
          "source_id": "s2", "color": "#00ff00", "marker_size": 7.0,
          "manual_fields": ["marker_size"],
        }],
      },
      active_source_id="s1",
    )
    overlay_styles = {
      item.source_id: item
      for item in overlay_prepared.resolved_presentation.presentation.source_styles
    }
    assert overlay_styles["s1"].marker_size == pytest.approx(4.0)
    assert overlay_styles["s2"].marker_size == pytest.approx(7.0)
    assert overlay_styles["s2"].color == "#00ff00"
  finally:
    widget.close()
    widget.deleteLater()

  export_path = tmp_path / "export-dot.png"
  _write_render_payload(
    export_path, prepared,
    {"s1": ((x_value,), (y_value,))}, {},
    BatchPlotExportSpec(
      id="dot-parity", name="Dot parity", width=width, height=height,
      include_title=False, include_axis_labels=False, include_ticks=False,
      include_gates=False, include_legend=False,
    ),
  )

  def dot_bbox(path):
    with Image.open(path) as image:
      pixels = np.asarray(image.convert("RGB"))
    left, top, right, bottom = margins
    plot_width = width - left - right
    plot_height = height - top - bottom
    center_x = round(left + x_value * plot_width)
    center_y = round(top + (1.0 - y_value) * plot_height)
    yy, xx = np.indices(pixels.shape[:2])
    local = (
      (xx >= center_x - 10) & (xx <= center_x + 10)
      & (yy >= center_y - 10) & (yy <= center_y + 10)
      & (pixels[:, :, 0] > 200)
      & (pixels[:, :, 1] < 200)
      & (pixels[:, :, 2] < 200)
    )
    ys, xs = np.where(local)
    assert len(xs) > 0
    return xs.min(), ys.min(), xs.max(), ys.max(), pixels

  gui_x0, gui_y0, gui_x1, gui_y1, gui_pixels = dot_bbox(gui_path)
  export_x0, export_y0, export_x1, export_y1, export_pixels = dot_bbox(export_path)
  assert (gui_x1 - gui_x0) == pytest.approx(export_x1 - export_x0, abs=1)
  assert (gui_y1 - gui_y0) == pytest.approx(export_y1 - export_y0, abs=1)
  gui_center = gui_pixels[(gui_y0 + gui_y1) // 2, (gui_x0 + gui_x1) // 2]
  export_center = export_pixels[(export_y0 + export_y1) // 2, (export_x0 + export_x1) // 2]
  # Both renderers source-over the same #ff0000 at alpha .60.  A few levels
  # of antialiasing variation are acceptable at the footprint edge.
  assert np.max(np.abs(gui_center.astype(int) - export_center.astype(int))) <= 12


def test_plot_widget_uses_the_presentation_axis_label_font(qapp) -> None:
  widget = PlotWidget()
  try:
    widget.set_presentation({
      "x_axis_display_label": "FSC-A",
      "y_axis_display_label": "SSC-A",
    })
    bottom_html = widget._plot_item.getAxis("bottom").label.toHtml()
    left_html = widget._plot_item.getAxis("left").label.toHtml()
    for html, label in ((bottom_html, "FSC-A"), (left_html, "SSC-A")):
      assert label in html
      assert "font-size:19px" in html
      assert "font-weight:700" in html
  finally:
    widget.close()
    widget.deleteLater()


def test_plot_widget_normalizes_tick_font_to_96_dpi_pixels(qapp) -> None:
  widget = PlotWidget()
  try:
    widget.set_presentation({
      "title_font": {"size": 14},
      "axis_label_font": {"size": 13},
      "tick_font": {"size": 12},
      "x_axis_display_label": "FSC-A",
      "y_axis_display_label": "SSC-A",
    })
    assert widget._plot_item.titleLabel.opts["size"] == "19px"
    assert widget._plot_item.getAxis("bottom").style["tickFont"].pixelSize() == 16
    assert widget._axis_label_text_style["font-size"] == "17px"
  finally:
    widget.close()
    widget.deleteLater()


def test_plot_widget_canvas_size_excludes_status_banner(qapp) -> None:
  widget = PlotWidget()
  try:
    widget.resize(800, 600)
    widget.set_status_banner("Preparing…")
    widget.show()
    qapp.processEvents()
    assert widget.canvas_size() == (widget._glw.width(), widget._glw.height())
    assert widget.canvas_size()[0] == widget.width()
    assert widget.canvas_size()[1] < widget.height()
  finally:
    widget.close()
    widget.deleteLater()


def test_plot_widget_reports_viewbox_margins_in_canvas_coordinates(qapp) -> None:
  widget = PlotWidget()
  try:
    widget.resize(800, 600)
    widget.set_status_banner("Preparing…")
    widget.show()
    qapp.processEvents()
    left, top, right, bottom = widget.plot_area_margins()
    width, height = widget.canvas_size()
    assert left >= 0 and top >= 0 and right >= 0 and bottom >= 0
    assert left + right < width
    assert top + bottom < height
  finally:
    widget.close()
    widget.deleteLater()


def test_qt_pdf_uses_the_same_logical_canvas_as_png(qapp, tmp_path) -> None:
  if shutil.which("pdftoppm") is None:
    pytest.skip("pdftoppm is required to rasterize PDF for this comparison")
  png_path = tmp_path / "plot.png"
  pdf_path = tmp_path / "plot.pdf"
  common = {
    "raw_layers": {"s1": (np.array([1.0, 10.0]), np.array([2.0, 20.0]))},
    "source_ids": ("s1",),
    "source_styles": {"s1": {"color": "#000000", "alpha": 0.6, "marker_size": 1.5}},
    "presentation": {
      "background_color": "#ffffff", "x_axis_display_label": "X",
      "y_axis_display_label": "Y", "show_grid": True,
    },
    "x_parameter": "x", "y_parameter": "y",
    "title_lines": ("Sample 1",), "title_colors": ("#4c78a8",),
    "x_transform": None, "y_transform": None,
    "x_range": (1.0, 10.0), "y_range": (2.0, 20.0), "gates": (),
    "width": 400, "height": 300,
    "options": BatchPlotExportSpec(
      id="export", name="Export", width=400, height=300, include_title=True,
      include_axis_labels=True, include_ticks=True,
    ),
    "export_metadata": {"scene_hash": "test-scene"},
  }
  render_batch_plot_qt(png_path, **common)
  render_batch_plot_qt(pdf_path, **common)
  raster_prefix = tmp_path / "pdf-raster"
  subprocess.run(
    ["pdftoppm", "-r", "72", "-png", "-singlefile", str(pdf_path), str(raster_prefix)],
    check=True, capture_output=True,
  )
  with (
    Image.open(png_path) as png_image,
    Image.open(raster_prefix.with_suffix(".png")) as pdf_image,
  ):
    assert png_image.size == pdf_image.size == (400, 300)
    png = np.asarray(png_image.convert("RGB"), dtype=np.float64)
    pdf = np.asarray(pdf_image.convert("RGB"), dtype=np.float64)
  normalized_rmse = float(np.sqrt(np.mean(np.square(png - pdf))) / 255.0)
  # The compatibility entry point now uses the core Pillow/PDF adapters.
  # Type1 glyph rasterisation differs from PNG, but the logical layout is
  # required to be identical and the bounded image difference must remain.
  assert normalized_rmse < 0.16
  png_layout = json.loads(
    png_path.with_suffix(png_path.suffix + ".json").read_text()
  )["plot_layout"]
  pdf_layout = json.loads(
    pdf_path.with_suffix(pdf_path.suffix + ".json").read_text()
  )["plot_layout"]
  assert png_layout == pdf_layout


def test_qt_batch_dpi_changes_sharpness_without_changing_layout(qapp, tmp_path) -> None:
  paths = {dpi: tmp_path / f"plot-{dpi}.png" for dpi in (96, 192)}
  values = np.linspace(1.0, 99.0, 120)
  for dpi, path in paths.items():
    render_batch_plot_qt(
      path,
      raw_layers={"s1": (values, 30.0 + values * 0.6)},
      source_ids=("s1",),
      source_styles={
        "s1": {"color": "#1864ab", "alpha": 0.65, "marker_size": 2.0}
      },
      presentation={
        "background_color": "#ffffff",
        "x_axis_display_label": "FITC B525-A",
        "y_axis_display_label": "APC R660-A",
        "show_grid": True,
      },
      x_parameter="x", y_parameter="y",
      title_lines=("Resolution check",), title_colors=("#1864ab",),
      x_transform=None, y_transform=None,
      x_range=(0.0, 100.0), y_range=(0.0, 100.0),
      gates=({
        "id": "gate", "name": "Gate", "gate_type": "rectangle",
        "x_parameter": "x", "y_parameter": "y",
        "thresholds": {"x_min": 55.0, "x_max": 80.0, "y_min": 55.0, "y_max": 80.0},
        "color": "#e00000",
      },),
      width=400, height=300,
      options=BatchPlotExportSpec(
        id=f"export-{dpi}", name="Export", width=400, height=300, dpi=dpi,
        raster_resolution_mode="dpi_scaled", include_title=True,
        include_axis_labels=True, include_ticks=True,
      ),
      export_metadata={"scene_hash": "same-scene"},
    )

  with Image.open(paths[96]) as low_image, Image.open(paths[192]) as high_image:
    assert low_image.size == (400, 300)
    assert high_image.size == (800, 600)
    normalized_high = high_image.convert("RGB").resize(
      low_image.size, Image.Resampling.LANCZOS
    )
    low = np.asarray(low_image.convert("RGB"), dtype=np.float64)
    high = np.asarray(normalized_high, dtype=np.float64)
  normalized_rmse = float(np.sqrt(np.mean(np.square(low - high))) / 255.0)
  # Text now includes the same readable minor labels as the live axis; the
  # additional glyph edges add a small, deterministic resampling difference.
  assert normalized_rmse < 0.055
