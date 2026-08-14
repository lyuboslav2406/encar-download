# Repository Review Context

## Project overview
- Python project to download vehicle pages/images from Encar and generate descriptions/posts using OpenAI models. Contains both a FastAPI-based application and a standalone external script used manually.

## Important entry points
- `main.py` — top-level runner (likely starts app).
- `app/routes.py` — FastAPI routes and web entrypoints.
- `external-script/encar_download2.py` — standalone script currently used manually (must be preserved).

## Standalone / local scripts
- `external-script/encar_download2.py` — standalone downloader/renderer that uses local `external-script/encar_images/` sample outputs.
- `external-script/encar_images/` — local debug/detail HTML and image files produced by the external script (excluded from archive by default as generated outputs).

## Application structure
- `app/` — application source modules:
  - `accident_service.py`, `cleanup.py`, `config.py`, `encar_options.py`, `feature_prompt.py`, `feature_selection.py`, `generator.py`, `image_service.py`, `legacy_post_generation.py`, `models.py`, `openai_service.py`, `pricing.py`, `report_service.py`, `routes.py`, `scraper.py`
- `static/` — frontend/static assets (`index.html`, icons, etc.)
- `tests/` — unit tests for application modules
- `external-script/` — external/manual script and its artifacts
- `generated/` — generated output folders (detail_page.html, JSON outputs). These are treated as generated data and excluded from the archive.

## Configuration and dependencies
- `requirements.txt` — Python dependencies (`fastapi`, `uvicorn`, `requests`, `beautifulsoup4`, `openai`, `python-multipart`, `jinja2`)
- `.gitignore` — updated to include local/generated patterns
- `app/config.py` — reads `OPENAI_API_KEY` and `OPENAI_MODEL` from environment variables

## Deployment
- No Dockerfile or cloud-specific deployment manifests found.

## Generated / local data (excluded from archive)
- `generated/` directories (many UUID-named folders and diagnostics folders)
- `external-script/encar_images/` (downloaded images and debug/detail HTML)
- Local virtual environment: `.venv/` (present in workspace; excluded)
- Python caches: `__pycache__`, `*.pyc`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`

## Potentially obsolete or uncertain files (kept)
- `.venv/` (virtualenv) — present but not included in archive; kept in repo (local development artifact)
- `generated/` — large generated outputs; left in repo but excluded from archive because status uncertain
- `external-script/encar_images/` — contains sample output images/HTML used by the external script; excluded from archive as likely generated

## Notes on secrets / environment
- No plaintext API keys or `.env` files with secrets were found in repository files. The code references `OPENAI_API_KEY` via environment variables in `app/config.py` and `external-script/encar_download2.py`.

