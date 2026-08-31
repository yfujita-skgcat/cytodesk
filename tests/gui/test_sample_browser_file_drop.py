"""Tests for external FCS file drops on the Samples list."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent  # noqa: E402

from flowdesk_core.fcs_io import FcsFileInfo  # noqa: E402
from flowdesk_core.models import ChannelSpec  # noqa: E402
from flowdesk_qt.sample_browser import (  # noqa: E402
  SampleBrowser,
  _validate_fcs_file_drop,
)

pytestmark = pytest.mark.gui


def _fcs_info() -> FcsFileInfo:
  return FcsFileInfo(
    fcs_version="3.1",
    instrument="",
    date="",
    sample="sample",
    event_count=10,
    channel_count=2,
    channels=(
      ChannelSpec(id="fsc", name="FSC-A"),
      ChannelSpec(id="ssc", name="SSC-A"),
    ),
    metadata={},
  )


def _mime_data(urls: list[QUrl]) -> QMimeData:
  data = QMimeData()
  data.setUrls(urls)
  return data


def _drop_event(data: QMimeData) -> QDropEvent:
  return QDropEvent(
    QPointF(1.0, 1.0),
    Qt.DropAction.CopyAction,
    data,
    Qt.MouseButton.NoButton,
    Qt.KeyboardModifier.NoModifier,
  )


def test_validate_fcs_file_drop_uses_local_urls_and_preserves_order(
  tmp_path: Path,
) -> None:
  first = tmp_path / "first sample.FCS"
  second = tmp_path / "日本語 second.fcs"
  directory = tmp_path / "directory.fcs"
  first.write_text("not a real FCS fixture")
  second.write_text("not a real FCS fixture")
  directory.mkdir()

  result = _validate_fcs_file_drop(_mime_data([
    QUrl.fromLocalFile(str(first)),
    QUrl("https://example.test/remote.fcs"),
    QUrl.fromLocalFile(str(directory)),
    QUrl.fromLocalFile(str(tmp_path / "notes.txt")),
    QUrl.fromLocalFile(str(second)),
  ]))

  assert result.paths == (str(first), str(second))
  assert len(result.rejected) == 3
  assert result.rejected[0][1] == "not a local file"
  assert result.rejected[1][1] == "directories are not supported"
  assert result.rejected[2][1] == "file extension is not .fcs"


def test_validate_fcs_file_drop_rejects_missing_and_non_url_payload(
  tmp_path: Path,
) -> None:
  missing = tmp_path / "missing.fcs"

  missing_result = _validate_fcs_file_drop(_mime_data([
    QUrl.fromLocalFile(str(missing)),
  ]))
  assert missing_result.paths == ()
  assert missing_result.rejected == ((str(missing), "file does not exist"),)

  assert _validate_fcs_file_drop(QMimeData()).paths == ()
  assert _validate_fcs_file_drop(QMimeData()).rejected == ()


def test_sample_list_drop_adds_valid_files_and_notifies_callbacks(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
  qapp,
) -> None:
  first = tmp_path / "first.fcs"
  second = tmp_path / "second.fcs"
  first.write_text("not a real FCS fixture")
  second.write_text("not a real FCS fixture")
  monkeypatch.setattr(
    "flowdesk_qt.sample_browser.read_fcs_info",
    lambda _path: _fcs_info(),
  )

  browser = SampleBrowser()
  callbacks: list[tuple[list[str], int]] = []
  browser.on_fcs_files_dropped(
    lambda paths, count: callbacks.append((paths, count))
  )
  try:
    data = _mime_data([
      QUrl.fromLocalFile(str(first)),
      QUrl.fromLocalFile(str(second)),
    ])
    event = _drop_event(data)
    browser._list_widget.dropEvent(event)

    assert event.isAccepted()
    assert event.dropAction() == Qt.DropAction.CopyAction
    assert [sample.path for sample in browser.samples()] == [
      str(first.resolve()),
      str(second.resolve()),
    ]
    assert callbacks == [([str(first), str(second)], 2)]
  finally:
    browser.close()
    browser.deleteLater()
    qapp.processEvents()


def test_sample_list_accepts_valid_file_drag_enter_and_move(
  tmp_path: Path,
  qapp,
) -> None:
  path = tmp_path / "sample.fcs"
  path.write_text("not a real FCS fixture")
  browser = SampleBrowser()
  try:
    data = _mime_data([QUrl.fromLocalFile(str(path))])
    enter_event = QDragEnterEvent(
      QPoint(1, 1),
      Qt.DropAction.CopyAction,
      data,
      Qt.MouseButton.NoButton,
      Qt.KeyboardModifier.NoModifier,
    )
    browser._list_widget.dragEnterEvent(enter_event)
    assert enter_event.isAccepted()
    assert enter_event.dropAction() == Qt.DropAction.CopyAction

    move_event = QDragMoveEvent(
      QPoint(1, 1),
      Qt.DropAction.CopyAction,
      data,
      Qt.MouseButton.NoButton,
      Qt.KeyboardModifier.NoModifier,
    )
    browser._list_widget.dragMoveEvent(move_event)
    assert move_event.isAccepted()
    assert move_event.dropAction() == Qt.DropAction.CopyAction
  finally:
    browser.close()
    browser.deleteLater()
    qapp.processEvents()


def test_sample_list_drop_ignores_rejected_only_payload(
  tmp_path: Path,
  qapp,
) -> None:
  browser = SampleBrowser()
  try:
    data = _mime_data([
      QUrl.fromLocalFile(str(tmp_path / "notes.txt")),
      QUrl("https://example.test/remote.fcs"),
    ])
    event = _drop_event(data)
    browser._list_widget.dropEvent(event)

    assert not event.isAccepted()
    assert browser.samples() == []
  finally:
    browser.close()
    browser.deleteLater()
    qapp.processEvents()
