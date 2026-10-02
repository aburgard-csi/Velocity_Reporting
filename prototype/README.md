# prototype/ — test-only deck experiments

`build_prototype.py` builds the redesigned Executive Review described in
`docs/STYLE-PROPOSAL-2026-10-02.md` from a client's launcher data pack and VIP sheets, so
the look can be judged on real figures before any builder changes.

**Not part of the pipeline.** Nothing in `build/`, `templates/` or `validation/` imports
it; the QA gate does not run on it; its output is never written to `Outputs/`. It imports
only `build/brand.py` (the palette) and `build/rpe_env.py` (fonts, logo helpers).

```
.venv/Scripts/python prototype/build_prototype.py <data_dir> <out.pptx>
```

`<data_dir>` holds `metrics.json`, `base.json`, `lift.json` (from
`Build Artifacts/launcher/<period>/<id>/`), the client's `<id>_ics.json` and
`<id>_mrpc.json` (from `Inputs/VIP Data/`) and a trimmed logo. First built 2026-10-02 for
Marine FCU 2026.09.
