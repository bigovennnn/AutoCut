# AutoCut Studio development guide

Read `CLOUD_SETUP.md`, `UPSTREAM.md` and `docs/VALIDATION.md` first. Preserve the pinned upstream license and attribution.

- The verified product entry is `cloud_app.py` with `src/open_storyline/quickcut/`; it is a bounded fixed workflow, distinct from the preserved upstream Agent.
- Everyday footage export is the current product priority. Lecture/interview editing remains future work; everyday samples are not lecture research evidence.
- Use Python 3.11 and `requirements-cloud.lock.txt` for the lightweight entry. Do not install the complete neural stack without an actual need.
- Start from `studio/` with `.venv/bin/python scripts/start_cloud.py`. Input defaults to `studio/uploads/`; `AUTOCUT_UPLOADS` overrides it.
- Required-stage failures stop the task. Optional-stage failures must be explicit. Never fabricate transcripts, provider results or successful exports.
- Preserve failures, original records and immutable export revisions. Measurements and displayed values must be traceable to real run records.
- Visual titles and genuine speech subtitles are separate. ASR text requires human review. Never fill unclear speech by guessing from the requested topic.
- Keep keys, private footage, resources and runtime artifacts out of Git. Patent drafts and unpublished research details remain local unless specifically authorized for publication.
- Preserve font identities, hashes, licenses and glyph checks. See `docs/FANCY_TITLE_WORKFLOW.md`.
- Test with `PYTHONPATH=src:. .venv/bin/python -m pytest tests/cloud -q`. Injected engineering fixtures are not AI effectiveness evidence.
- The repository root contains the historical prototype. Do not describe its simulated Streamlit outputs as verified processing.
