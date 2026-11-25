---
name: fix-deck-failure
description: Triage and fix a deck that fails the validation gate (validate_deck.py reports a FAIL, Sheila says Needs attention, or the launcher says Not put in Outputs). Use when a build or rebuild fails validation for one or many clients. Finds the FAIL, classifies it, proves the fix on a copy, fixes the builder with a test that fails on the old code, renders the slide, and ships through a PR and a rebuild.
---

# Fix a deck that fails the gate

A deck with any FAIL never reaches Outputs (the launcher keeps the old deck), so a FAIL costs a CSM their deck until it
is fixed. CLAUDE.md is strict about how: **fix the BUILDER and the template shell, never the deck**, and when a defect
got through the gate, add the check that would have caught it. Do not override the gate and do not lower a rule to pass.

## 1. Find the FAIL

The launcher keeps the validator's full report beside the built deck:

```
Build Artifacts/launcher/<period>/<id>/<deck>.pptx.validation.txt     # every finding; FAIL lines start "[FAIL"
Build Artifacts/launcher/<period>/<id>/build.log                       # the build's steps, for a build that stopped earlier
Build Artifacts/launcher/<period>/<id>/_launcher_result.json           # result, delivered
```

(TI and Companion builds keep theirs under `.../<id>/ti/` and `.../<id>/companion/<id>/`.) Note the slide number, the rule's
message, and whether the same FAIL hits other clients: grep the other clients' `.validation.txt` files for the same message.
One rule failing on every deck of a program points at a shared builder; one client alone points at its data.

## 2. Classify it

- **Builder or template defect**: the code draws something the rule correctly rejects (text wraps into the next row, a
  stale template caption, a source note naming the wrong client). Most FAILs are this. Fix in `build/` or `templates/`.
- **Data defect**: the input is wrong or missing (an unmapped code, an unevaluated workbook, a stale extract). Do not
  touch the builder to hide it: say what is wrong with which input and who fixes it (the data team, the CSM's code
  sheet). "Missing source data is stated, never zeroed" (CLAUDE.md).
- **Validator false positive**: the slide is right and the rule misreads it. Prove it with the rendered slide (step 5)
  before touching `validation/validate_deck.py`, and pin the case in that rule's tests (half of
  `tests/test_claim_consistency.py` is such cases). Rare; never the first assumption.

## 3. Reproduce the fix on a COPY

Copy the failed deck into the scratchpad and work on the copy only; the original is the evidence.

1. Redraw the failing slide on the copy with the fixed code (call the builder function that draws it, e.g.
   `shapes.draw_contact_slide(slide, contacts)`, on that slide of the copy, then save the copy).
2. Validate the copy:
   ```
   python -c "import sys; sys.path[:0]=['validation','build']; import validate_deck as V; [print(l, s, m) for l, s, m in V.run(sys.argv[1]) if l == 'FAIL']" "<copy>.pptx"
   ```
   `validate_deck.run(path)` returns `[(level, slide, message)]`, FAIL first. Zero FAIL lines on the copy is the target.

## 4. Fix the builder, with a test that fails on the old code

Work in a scratch worktree on a new branch from `origin/main` (never the main checkout, never the tasks checkout).

1. Make the fix in the builder (`build/...`, or the template shell plus `templates/TEMPLATES.md`).
2. Add a test that exercises it (the worked example's is `tests/test_contact_slide.py`). Prove it bites: keep the fixed
   file aside, put the old one back (`git show origin/main:<path> > <path>`), run the test and SEE IT FAIL, then restore
   the fixed file and see it pass. A test that passes on the old code catches nothing.
3. If the gate let the defect through (a deck that passed but was wrong), add the check to `validation/validate_deck.py`
   too (standing rule, Aaron 2026-08-17).
4. Run the gate for a change to `build/`, `templates/` or `validation/`:
   `python validation/qa_all.py` from the repo `.venv`, and the unit suite as CI runs it (merge-and-release skill,
   section 3). Review any DRIFT; `--snapshot` only for a layout change you meant.

## 5. Render the slide and look at it

The gate does not prove a slide looks right. Render it with PowerPoint (COM, read-only, no window):

```
powershell -ExecutionPolicy Bypass -File C:\Users\aaron.burgard\.claude\skills\ils-prep-deck\reference\render.ps1 -Deck "<copy>.pptx" -Slides "<n>" -Out "<scratchpad>\render-<n>-<stamp>"
```

**Always a NEW `-Out` folder**: it does not always overwrite, and an old PNG looks exactly like a fresh one. Open the PNG
with Read and look: the fixed element, and that nothing else on the slide moved.

## 6. Ship it

1. CHANGELOG entry (starts `Summary:`), commit, push, PR. No client names or figures in the PR.
2. **STOP: merge and release only on Aaron's word** (the `merge-and-release` skill). The launcher runs the released code,
   so the fix reaches nobody until it is released.
3. **Rebuild every affected client** (the `rebuild-decks` skill), not only the one that was reported, and confirm each
   is in Outputs with 0 FAIL.

## Worked example (2026-11-24)

After #155 centred the Contact Us text, the ICS program contact's long title (wider than its column at 18 pt) wrapped out
of its one-line box into the phone row. Every ICS deck failed `one-line label wraps and collides` on rebuild and stayed out
of Outputs. A builder defect: the fix gave `shapes.draw_contact_slide` a two-line role box when any role needs it, moving
phone and email down one line in every column (#199, `tests/test_contact_slide.py`), then a release and a rebuild of the
ICS decks.

## Gotchas

- **Never edit the failed deck** to make it pass, and never ship a deck from `Build Artifacts/` by hand: the next build
  draws the defect again, and a hand-fixed deck is indistinguishable from a built one.
- **A FAIL on many clients is one fix**, not many: find the shared builder before touching anything per client.
- **python-pptx is not the file**: a deck can pass every text rule and not open; the package check
  (`validate_deck.package_findings`) is the only rule that sees it (CLAUDE.md, QA gate).
- **Nominal font size is not rendered size**: look at the render, not the XML.
- **render.ps1 opens the deck read-only**, then calls `Quit()` and stops any windowless POWERPNT left holding it. COM
  attaches to a PowerPoint that is already running, so if Aaron has PowerPoint open, ask before rendering. Render a
  copy, never a file he has open.
- **No client data in git**: decks, renders and validation reports stay in the scratchpad or `Build Artifacts/`.
