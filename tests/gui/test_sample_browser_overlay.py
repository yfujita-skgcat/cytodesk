from __future__ import annotations

from types import SimpleNamespace

import pytest

from flowdesk_qt.sample_browser import SampleBrowser, _SampleInfo

pytestmark = pytest.mark.gui

_EMPTY_INFO = SimpleNamespace(event_count=0)


def test_clear_overlay_color_removes_only_manual_color(qapp) -> None:
  browser = SampleBrowser()
  states: list[dict[str, object]] = []
  browser.on_overlay_changed(states.append)
  browser._samples = [_SampleInfo("sample-a", "Sample A", "", _EMPTY_INFO)]
  browser._manual_overlay_sample_ids = {"sample-a"}
  browser._manual_overlay_colors = {"sample-a": "#123456"}
  browser._overlay_roles = {"sample-a": "positive_control"}

  browser._clear_overlay_color("sample-a")

  state = browser.overlay_state()
  assert state["manual_overlay_sample_ids"] == ["sample-a"]
  assert state["manual_overlay_colors"] == {}
  assert state["overlay_roles"] == {"sample-a": "positive_control"}
  assert states[-1] == state
  browser.close()
  browser.deleteLater()
  qapp.processEvents()


def test_clear_samples_resets_project_overlay_state(qapp) -> None:
  browser = SampleBrowser()
  try:
    browser._samples = [
      _SampleInfo("old-a", "Old A", "", _EMPTY_INFO),
      _SampleInfo("old-b", "Old B", "", _EMPTY_INFO),
    ]
    browser.set_overlay_state(
      ["old-a", "old-b"],
      {"old-a": "#123456"},
      {"old-b": "positive_control"},
      [{
        "id": "pair",
        "members": [{"sample_id": "old-a"}, {"sample_id": "old-b"}],
      }],
      "manual_plus_comparison",
    )

    browser.clear_samples()

    assert browser.overlay_state()["manual_overlay_sample_ids"] == []
    assert browser.overlay_state()["manual_overlay_colors"] == {}
    assert browser.overlay_state()["overlay_roles"] == {}
    assert browser.overlay_state()["comparison_sets"] == []
    assert browser.overlay_state()["overlay_mode"] == "manual_only"
  finally:
    browser.close()
    browser.deleteLater()
    qapp.processEvents()


def test_overlay_state_drops_unknown_comparison_members(qapp) -> None:
  browser = SampleBrowser()
  try:
    browser._samples = [
      _SampleInfo("new-a", "New A", "", _EMPTY_INFO),
      _SampleInfo("new-b", "New B", "", _EMPTY_INFO),
    ]
    browser.set_overlay_state(
      [],
      comparison_sets=[{
        "id": "pair",
        "members": [
          {"sample_id": "old-a"},
          {"sample_id": "new-a"},
          {"sample_id": "new-b"},
        ],
      }],
      overlay_mode="manual_plus_comparison",
    )

    assert browser.overlay_state()["comparison_sets"] == [{
      "id": "pair",
      "members": [{"sample_id": "new-a"}, {"sample_id": "new-b"}],
    }]
  finally:
    browser.close()
    browser.deleteLater()
    qapp.processEvents()


def test_default_overlay_color_is_available_for_sample_row(qapp) -> None:
  browser = SampleBrowser()
  try:
    assert browser.overlay_color("unknown") == "#4c78a8"
  finally:
    browser.close()
    browser.deleteLater()
    qapp.processEvents()


def test_overlay_state_follows_sample_list_order(qapp) -> None:
  browser = SampleBrowser()
  try:
    browser._samples = [
      _SampleInfo("top", "Top", "top.fcs", None),
      _SampleInfo("bottom", "Bottom", "bottom.fcs", None),
    ]
    browser._manual_overlay_sample_ids = {"top", "bottom"}
    assert browser.overlay_state()["manual_overlay_sample_ids"] == ["top", "bottom"]
  finally:
    browser.close()
    browser.deleteLater()
    qapp.processEvents()
