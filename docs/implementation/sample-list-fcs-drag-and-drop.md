# Sample Browser FCS drag-and-drop

## Status

Increment 1 is implemented. Increment 2 and Increment 3 remain pending. This
guide is not an authorization to change the FCS model, pipeline, or project
schema.

## Goal

Allow users to drag one or more local `.fcs` files from the operating system's
file manager onto the Samples list. The feature must work through Qt's common
file-URL interface on Linux (including GNOME Files), Windows Explorer, and
macOS Finder.

The existing internal drag operation, which changes canonical sample order,
must continue to work unchanged.

## Scope

- Accept one or more local file URLs from `QMimeData.urls()`.
- Convert URLs with `QUrl.toLocalFile()`; do not parse `file:` URLs manually.
- Accept `.fcs` case-insensitively and preserve the order supplied by the
  file manager.
- Reuse the existing `SampleBrowser.add_samples_from_paths()` validation,
  duplicate-path handling, stable-ID generation, and FCS metadata loading.
- Route the Samples-pane button, File -> Add FCS Files..., and file drop
  through the same MainWindow import/session path.
- Keep raw event data immutable and do not run the pipeline automatically.

## Non-scope

- Do not accept HTTP, cloud, or other non-local URLs and do not download them.
- Do not recursively scan a dropped directory. Show a message directing the
  user to Add FCS Directory... instead.
- Do not add FCS parsing, compensation, transforms, gates, statistics, or
  other scientific execution to the Qt widget.
- Do not replace or rename the existing internal sample-order drag behavior.
- Do not change project schema or sample identity semantics unless a separate
  migration guide is added and approved.

## Current architectural constraint

`SampleBrowser._SampleListWidget` already uses `QAbstractItemView.InternalMove`
and emits an order change after an internal drop. External file drops must be
recognized before calling the base `dropEvent`; otherwise Qt may treat the
file URLs as an item move or insert an unintended list item.

`SampleBrowser._on_add_files()` currently owns a separate file dialog path,
while `MainWindow._on_open_files()` owns project dirty-state and file-dialog
history. The implementation must remove this behavioral split at the UI
entry-point level without moving FCS parsing out of `flowdesk_core`.

## Implementation contract

### 1. MIME and drag-event handling

Add a small Qt-side helper, preferably independently testable, that receives a
`QMimeData` and returns local, existing `.fcs` paths plus rejected URL details.
It must:

- check `hasUrls()`;
- require `QUrl.isLocalFile()`;
- call `toLocalFile()`;
- reject empty paths, directories, and non-`.fcs` suffixes;
- compare suffixes case-insensitively;
- avoid shell-specific separators and string slicing;
- retain URL order and never mutate the source `QMimeData`.

In `_SampleListWidget`:

- internal drags (`event.source() is self`) continue through the existing
  reorder path;
- external drags accept `CopyAction` only when at least one valid local FCS
  URL is present;
- `dragMoveEvent` uses the same validation as `dragEnterEvent`;
- external `dropEvent` emits a path-list signal and does not call the base
  item-drop implementation;
- rejected-only drops are accepted as handled only if a user-visible reason
  is shown, otherwise they are ignored.

Do not depend on platform-specific native drag APIs. Qt's `QUrl` conversion is
the portability boundary for GNOME Files, Explorer, and Finder.

### 2. Shared import/session path

Add a SampleBrowser signal or callback for an external FCS drop. Make the
Samples-pane Add FCS Files... button notify MainWindow instead of directly
owning a second import implementation. MainWindow should provide one shared
operation for menu, button, and drop:

1. normalize the received paths without changing their meaning;
2. call the existing `add_samples_from_paths()` API;
3. mark the project dirty only when at least one sample was added;
4. keep existing samples, overlays, gates, and sample order state intact;
5. report added, duplicate, unsupported, and unreadable files without a
   traceback or silent failure;
6. leave pipeline results and execution caches subject to the same existing
   import behavior; do not start a run implicitly.

The current public return value of `add_samples_from_paths()` is an integer.
Keep that compatibility unless a separate result type is introduced with a
fully tested compatibility wrapper.

### 3. UI feedback and accessibility

While a valid external FCS drag is over the list, show a platform-neutral
highlight or status hint such as “Drop FCS files to add”. Clear the state on
drop, cancel, leave, and widget destruction. Keep stable object names for the
list and add button. The list tooltip and manual must explain that dropped
files are added to the current session and do not open a project.

### 4. Ordering and identity

Use the same canonical ordering and duplicate rules as Add FCS Files.... In
manual mode, the received order must be preserved. Do not generate IDs from
display names; retain the existing resolved-path/fingerprint identity rules.
Unicode names, spaces, symlinks, and Windows drive/UNC paths must be passed
through `Path` and Qt APIs without ad-hoc normalization.

## Increment plan

Only one increment may be implemented in a single LLM run.

### Increment 1 — External URL seam without regression

- Add the pure MIME URL helper and `_SampleListWidget` external drag/drop
  branch.
- Preserve internal reorder behavior and current sample ordering.
- Add unit/GUI tests for local FCS, uppercase suffix, Unicode/space paths,
  mixed invalid URLs, directories, remote URLs, and internal reorder.

### Increment 2 — Shared import and session state

- Route menu, Samples-pane button, and drop through the same MainWindow import
  method.
- Add tests for dirty-state, duplicate handling, partial failure feedback,
  preserving existing samples, and no implicit pipeline execution.
- Confirm close/open project and save/load behavior remain isolated.

### Increment 3 — Documentation, native validation, and release checks

- Update `docs/user-manual/user_manual.md` with the user workflow and limits.
- Add targeted GUI tests to the native Linux, Windows, and macOS package
  workflows where feasible.
- Manually verify the packaged application using GNOME Files, Windows
  Explorer, and macOS Finder, including Unicode and spaces in filenames.
- Record any platform-specific limitation (for example, future macOS
  sandbox/security-scoped URL requirements) rather than silently weakening
  validation.

## Target files

- `src/flowdesk_qt/sample_browser.py`
- `src/flowdesk_qt/main_window.py`
- `tests/gui/test_sample_browser_file_drop.py` (new)
- Existing SampleBrowser/MainWindow GUI tests as needed
- `docs/user-manual/user_manual.md`
- `.github/workflows/package-linux.yml`
- `.github/workflows/package-windows.yml`
- `.github/workflows/package-macos.yml`

## Required tests

- Pure helper tests use `QUrl.fromLocalFile()` and do not construct platform
  specific URI strings.
- A single valid file is added exactly once.
- Multiple valid files retain drop order.
- Duplicate paths, unreadable FCS files, directories, non-FCS files, and
  non-local URLs are reported and never crash the GUI.
- Existing samples and their stable IDs remain unchanged.
- Internal list reorder still emits the canonical order and never emits an
  import request.
- Menu, button, and drop have identical dirty-state and status behavior.
- Project save/load after a drop preserves the added sample paths.
- No worker, pipeline, or Qt thread is started solely by dropping files.
- Targeted tests pass on the native Linux, Windows, and macOS package jobs;
  native file-manager testing is additionally recorded as manual evidence.

## Acceptance criteria

The feature is complete only when all of the following are true:

- A user can drop one or more local `.fcs` files onto the Samples list on all
  three advertised operating systems.
- Internal sample reordering still works exactly as before.
- All three import entry points use one shared session/import operation.
- Invalid and duplicate inputs produce clear feedback and no traceback.
- Project dirty state, stable sample IDs, save/load, and existing analysis
  state are not regressed.
- No scientific execution logic or raw-event mutation was added to Qt.
- The user manual, implementation guide, tests, and remaining limitations are
  updated before marking the ToDo item complete.
