# Transform, population color, and settings-save bug follow-up

## Scope

This guide covers four field-reported defects found after the transform,
population-color, Batch Plot Export, and Analysis Settings features were
integrated.  The reports are valid, but the first report's proposed cause needs
one correction: creating a second versioned transform for one parameter is an
intentional core capability.  The defect is that storage and the editor still
enforce an obsolete one-transform-per-parameter restriction.

Read `AGENTS.md`, `docs/implementation/llm-task-protocol.md`, this guide, and
the related guides below before changing production code.  Implement exactly
one numbered increment per LLM run.

Related guides:

- `scientific-transforms-v2.md`
- `analysis-workflow-integration.md`
- `current-view-export-batch-parity.md`
- `analysis-settings-bundles.md`
- `project-migration-and-recovery.md` when a persisted format changes

## Investigation result

| Report | Assessment | Verified cause |
|---|---|---|
| Axis Transform switching makes a project unsavable | Valid, high severity | With any gate present, `MainWindow._on_axis_analysis_transform_requested()` preserves the old immutable transform and creates/reuses another version. This agrees with the versioned-transform design, but `flowdesk_storage.manifest._validate_current_transforms()` and `TransformEditorDialog._validate_all()` still reject two transforms for the same parameter. |
| Deleting an unused transform reports `Transform is used by gates` | Valid | `TransformEditorDialog.transforms()` commits the row selected after deletion. `_build_current_spec()` reconstructs `TransformSpec` without the persisted `notes`, so an otherwise untouched neighboring transform changes. `MainWindow._on_edit_transforms()` correctly notices that the gate-referenced mapping is no longer identical and blocks the whole update. |
| Batch Plot Export paints a child population with its parent's color | Valid | The GUI paints masks in hierarchy/depth precedence, while `flowdesk_cli.batch_plot._population_event_colors()` iterates the persisted color mapping directly. Mapping/insertion order and random gate IDs are not a population precedence contract, so a parent can be painted after its child. |
| Save Analysis Settings creates a sibling and strips dotted names | Valid UX/path bug, not a desirable specification | The action uses `getExistingDirectory()` as though the user were choosing a destination directory, then treats that selected directory as a bundle basename. `Path.with_suffix(".flowdesk-settings")` replaces a final suffix, so `exp1.v2` becomes `exp1.flowdesk-settings`. |

## Shared contracts

- Raw events, transform mathematics, gate coordinates, memberships, counts,
  frequencies, statistics, and analysis revision must not change merely from
  opening an editor, exporting a plot, or choosing a save path.
- A transform ID is unique and immutable while referenced.  More than one
  versioned analysis transform may target the same stable parameter ID.
- A gate axis and a plot view select a transform by exact transform ID.  Code
  must not infer one active version from collection order when several versions
  target the same parameter.
- Population color is display-only.  The deepest containing descendant wins;
  sibling overlap follows persisted display `z_order`, then stable hierarchy
  order, then stable population ID.  GUI and headless export use one core
  resolver for that rule.
- `.flowdesk-settings` is a directory bundle whose terminal suffix is appended
  literally to the entered bundle name.  It is not produced by replacing an
  arbitrary filename suffix.
- Update `docs/user-manual/user_manual.md` in the same increment as each
  user-visible production change.

## Increment 1 — Restore the versioned-transform storage contract

### Purpose

Make projects containing an old gate-bound transform and a newly selected
transform for the same parameter valid, saveable, reloadable, and executable
headlessly.  Do not solve this by mutating an old gate's transform or silently
deleting a referenced definition.

### Inspect first

- `src/flowdesk_storage/manifest.py`
- `src/flowdesk_core/models.py`
- `src/flowdesk_core/pipeline_runner.py`
- `src/flowdesk_qt/main_window.py` transform lookup, axis selection, gate
  creation, plot-view save/load, and transform-reference helpers
- `schemas/project.schema.json`
- transform and project-storage tests

### Required implementation

1. Remove the obsolete parameter-uniqueness rejection from current-manifest
   validation.  Keep unique transform IDs, valid roles/types/settings, stable
   parameter IDs, and every gate/view/statistic reference fully validated.
2. Preserve the existing quick-selector behavior:
   - reuse an exact parameter/type/settings match;
   - replace an unreferenced quick-created definition when safe;
   - preserve a referenced definition and create/select a new immutable ID when
     the requested transform differs.
3. Audit all parameter-only transform lookups.  A parameter-only lookup may be
   used only as a backwards-compatible fallback when exactly one definition
   matches.  With multiple matches, require an explicit plot-view, gate-axis,
   or statistic transform ID and emit a diagnostic if that binding is absent.
4. Persist the currently selected plot transform ID so save/reload does not
   depend on transform list order.  Existing gates retain their old IDs and
   newly drawn gates capture the current selected ID.
5. Keep current-format compatibility.  This fix relaxes an accidental
   validator restriction and should not rewrite valid transform IDs or gate
   coordinates.  Raise the project format only if schema semantics actually
   need a migration.

### Required tests

- Create Asinh for parameter X, bind an existing gate to it, switch X to Log10,
  save, reload, and run `PipelineRunner`; both IDs remain present and the old
  gate still references Asinh.
- Draw a new gate after the switch and verify that it references Log10.
- Save/load preserves the active plot-view transform ID and does not choose the
  first transform in registry order.
- Duplicate transform IDs, missing transform references, wrong-parameter gate
  bindings, and invalid settings still fail validation.
- Existing single-transform projects round-trip byte-semantically without a
  forced migration.

### Acceptance criteria

- The reported `parameter ... has more than one analysis transform` save error
  is absent for a valid versioned project.
- GUI preview, saved project, reload, CLI, and headless runner resolve the same
  explicit transform IDs.
- No existing gate membership changes merely because the plot axis selects a
  newer transform version.

## Increment 2 — Make Transform Editor commits lossless

### Purpose

Deleting an unreferenced transform must not mutate the automatically selected
neighbor.  The editor must also support the multiple transform versions made
valid by Increment 1.

### Inspect first

- `src/flowdesk_qt/transform_editor.py`
- `src/flowdesk_qt/main_window.py` (`_on_edit_transforms`)
- `tests/gui/test_transform_editor.py`
- focused transform-reference GUI tests

### Required implementation

1. Build an edited row by merging the visible editable fields into a deep copy
   of that row, or by using an equivalent typed replacement.  Preserve `role`,
   `notes`, and every persisted field that the dialog does not expose.
2. Selection changes caused by Delete, list refresh, or initial loading must not
   mark or reconstruct the newly selected row.  Prefer explicit dirty tracking
   per row so `OK` commits only genuine edits; at minimum, a no-op edit must be
   mapping-equivalent to its input.
3. Remove the editor's one-transform-per-parameter validation.  Continue to
   reject duplicate transform IDs and invalid definitions.  Make list labels
   sufficient to distinguish multiple versions for one parameter.
4. Keep gate-referenced transform IDs immutable.  Deleting or changing a
   scientific field (`parameter`, `transform_type`, or `settings`) of a
   referenced definition remains blocked unless an explicit migration command
   is used.  Do not weaken this guard to work around accidental metadata loss.
5. Apply accepted changes atomically.  A rejected referenced edit must leave
   the entire project transform registry unchanged.

### Required tests

- Start with an unused row adjacent to a gate-referenced row whose `notes` are
  `Created from the axis Transform selector.`; delete the unused row and press
  OK.  The operation succeeds and the referenced mapping remains identical.
- Change list selection and press OK without editing; all mappings, including
  `notes` and `role`, remain identical.
- Two valid transforms for one parameter can be displayed, edited when
  unreferenced, accepted, saved, and reopened.
- Deleting or changing a referenced scientific definition is still rejected
  atomically.
- Cancel leaves the source registry unchanged.

### Acceptance criteria

- The reported false `Transform is used by gates` warning is eliminated.
- No hidden/provenance field is lost during a no-op dialog round trip.
- Actual referenced-transform changes remain protected.

## Increment 3 — Share population-color precedence with Batch Plot Export

### Purpose

Use one renderer-neutral precedence implementation for GUI preview and Batch
Plot Export so descendants cannot be overwritten by ancestors because of map
or ID order.

### Inspect first

- `src/flowdesk_core/integrated_overlay.py`
- `src/flowdesk_qt/main_window.py` (`_population_event_colors`)
- `src/flowdesk_cli/batch_plot.py` (`_population_event_colors`)
- `tests/test_integrated_overlay.py`
- `tests/test_cli_batch_plot.py`, `tests/test_plot_export_reuse.py`, and focused
  GUI population-color tests

### Required implementation

1. Extend the existing core population-color resolver with a vectorized event-
   mask resolver or a canonical paint-order helper.  It must implement exactly
   this winner order: deepest population, smallest persisted `z_order`, earliest
   stable hierarchy order, then stable population ID.
2. Derive depth from the validated parent graph, not from gate ID text.  Reject
   or diagnose missing parents/cycles through existing project validation; do
   not invent a depth from collection order.
3. Make both GUI and CLI/Batch adapters call the core helper.  Do not import Qt
   code into core or import `MainWindow` behavior into the CLI.
4. Apply population colors only to existing authoritative membership masks.
   Do not re-evaluate gates in the renderer and do not use display-downsampled
   points to calculate membership.
5. Preserve overlay-source color precedence and density-mode exclusion.  This
   increment changes only the ordering among population display colors.

### Required tests

- P3 parent and P4 child use IDs deliberately arranged in both lexical orders;
  P4 events use the P4 color in GUI and Batch output in both cases.
- A three-level hierarchy always paints the deepest containing descendant.
- Overlapping siblings follow `z_order`, hierarchy order, and ID fallback
  deterministically.
- GUI and Batch produce the same per-event color array before rendering and the
  same overlap-center color in PNG output.
- Color changes/export leave memberships, counts, frequencies, statistics, raw
  events, and pipeline revision unchanged.

### Acceptance criteria

- Parent/child color output is independent of random gate IDs and serialized
  mapping order.
- GUI preview, GUI-triggered Batch export, and CLI Batch export use the same
  population-color precedence and provenance.

## Increment 4 — Make Analysis Settings save destination unambiguous

### Purpose

Let the user choose a bundle name, preserve dots in that name, and clearly show
where the `.flowdesk-settings` directory bundle will be created.

### Inspect first

- `src/flowdesk_qt/main_window.py` (`_on_save_analysis_settings` and dialog
  history helpers)
- `src/flowdesk_storage/analysis_settings.py`
- `tests/gui/test_analysis_settings.py`
- `tests/test_analysis_settings.py`
- `docs/user-manual/user_manual.md`

### Required implementation

1. Replace the existing-directory chooser with a save-name workflow (for
   example, `QFileDialog.getSaveFileName`) whose label/filter explains that the
   result is a `.flowdesk-settings` directory bundle.
2. Centralize target normalization in a pure helper.  If the entered name does
   not already end in `.flowdesk-settings`, append that exact terminal string.
   Never use `Path.with_suffix()` for this operation.  Thus `exp1.v2` becomes
   `exp1.v2.flowdesk-settings`, while an already suffixed name remains unchanged.
3. Remember the parent directory of the final target in file-dialog history.
   Cancel must not update history or create anything.
4. If a target exists, use an explicit replacement confirmation.  Replace only
   a recognized settings bundle through the existing atomic storage operation;
   reject an arbitrary non-bundle directory instead of deleting or reusing it.
5. Keep save failure atomic and report the final resolved path in status/error
   text.  Loading behavior and bundle contents do not change in this increment.

### Required tests

- Normalize `exp1`, `exp1.v2`, `exp1.flowdesk-settings`, Unicode/space names,
  and parent directories containing dots.
- Mock the GUI save dialog and verify the created target, history parent,
  cancellation, existing-bundle confirmation, and non-bundle rejection.
- Verify Windows-style cases with `PureWindowsPath` or a platform-neutral name
  component helper rather than assuming POSIX suffix rules.
- Storage round-trip and atomic failure tests continue to pass.

### Acceptance criteria

- Entering `D:\\FACS\\exp1` resolves to
  `D:\\FACS\\exp1.flowdesk-settings` because `exp1` is the chosen bundle name,
  and the save UI no longer presents it as an existing destination folder.
- Entering `D:\\FACS\\exp1.v2` resolves to
  `D:\\FACS\\exp1.v2.flowdesk-settings`; no part of the name is discarded.
- The user manual describes the save-name behavior, suffix rule, replacement
  prompt, and directory-bundle nature.

## Final verification

Run focused tests for each increment first, then the project checks required by
`AGENTS.md`.  At minimum the completed four-increment series must run:

```bash
.direnv/python-3.12.13/bin/python -m pytest -q \
  tests/test_project_storage.py \
  tests/test_pipeline_runner.py \
  tests/test_integrated_overlay.py \
  tests/test_cli_batch_plot.py \
  tests/test_analysis_settings.py
./tools/run-gui-tests.sh -q
.direnv/python-3.12.13/bin/ruff check src tests
.direnv/python-3.12.13/bin/mypy src/flowdesk_core src/flowdesk_storage src/flowdesk_cli
```

Record baseline failures separately.  Do not weaken scientific assertions or
approve a visual fix that changes authoritative gate membership.
