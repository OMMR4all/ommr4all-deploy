# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**OMMR4all-deploy** is the deployment orchestration repository for OMMR4all (Optical Music Recognition for All), a web platform for OMR. It wires together a Django REST API backend, an Angular frontend, and several Python ML modules via Git submodules.

## Repository Structure

All major components live under `modules/` as Git submodules:

- `modules/ommr4all-server/` — Django 5.2 backend (Python 3.12+), the core application
- `modules/ommr4all-client/` — Angular 21 frontend SPA
- `modules/ommr4all-line-detection/` — ML module for staff line detection
- `modules/ommr4all-layout-analysis/` — ML module for page layout analysis
- `modules/ommr4all-page-segmentation/` — ML module (excluded from uv workspace)
- `modules/calamari/` / `modules/nautilus/` — external OCR/OMR libraries

Deployment logic lives in `ommr4all-deploy/`:
- `deploy.py` / `deploy/run_deploy.py` — full production deploy (builds client, configures Django, restarts Apache2)
- `test.py` / `test/run_test.py` — CI test runner (sets up venv, runs migrations, runs Django tests)

## Development Setup

### Backend (Django server)

```bash
cd modules/ommr4all-server

# Install dependencies (use uv from root, or pip inside the server module)
uv sync                          # from repo root — installs all workspace packages
# or legacy:
pip install -r requirements.txt

# Apply migrations
python manage.py migrate

# Run development server
python manage.py runserver
```

### Frontend (Angular client)

```bash
cd modules/ommr4all-client

npm install

# Serve in dev mode (English)
npm start                   # ng serve

# Serve German locale
npm run start-de

# Production build (English + German)
npm run build-prod
```

## Running Tests

All test commands run from the Django server module:

```bash
cd modules/ommr4all-server

# Run all tests
python manage.py test

# Run a single test module
python manage.py test tests.test_restapi

# Run a single test class
python manage.py test tests.test_restapi.GenericTests

# Run a single test method
python manage.py test tests.test_restapi.GenericTests.test_ping
```

Test fixtures and storage live in `modules/ommr4all-server/tests/storage/` and `tests/raw_storage/`.

## Linting

```bash
# Frontend
cd modules/ommr4all-client
npm run lint                 # ng lint

# Backend — no linter is configured; check pyproject.toml if one is added
```

## CI/CD Pipeline (`.gitlab-ci.yml`)

Three environments map to three deployment paths:

| Branch/Tag | Test | Deploy | Runner tag |
|---|---|---|---|
| `dev` | `python3 ommr4all-deploy/test.py` | — | `deployment-master` |
| `master` | same | `python3 ommr4all-deploy/deploy.py` | `deployment-master` |
| version tag | same | `python3 ommr4all-deploy/deploy.py --gpu` | `deployment-production` |

## Docker

```bash
# Build and start (set STORAGE and PORT env vars first)
docker-compose up -d

# Create superuser
docker-compose run /opt/ommr4all/ommr4all-deploy-venv/bin/python \
  /opt/ommr4all/ommr4all-deploy/modules/ommr4all-server/manage.py createsuperuser
```

The image is `uniwue/ommr4all`, exposes port 8001, mounts storage at `${STORAGE}:/opt/ommr4all/storage`, and serves via Apache2 + mod_wsgi.

## Key Architecture Notes

- **Django settings** are dynamically rewritten during deployment (`run_deploy.py` patches `ALLOWED_HOSTS`, `DEBUG`, `SECRET_KEY`, and the database path via sed).
- **Static files** are collected by `manage.py collectstatic` during deploy and served by Apache under an alias; in dev they are served by Django or the Angular dev server.
- **WebSocket support** is provided by Django Channels; routing is in `modules/ommr4all-server/ommr4all/routing.py`.
- **Package manager**: The workspace uses `uv` (see `pyproject.toml` and `uv.lock`). The legacy deploy scripts still create pip-based virtualenvs targeting Python 3.8; the workspace itself requires Python ≥3.12.
- **Submodule hashes** are validated during test runs by `tests/manage_gitlab-ci.py` — if submodules are updated, that file must be updated accordingly.
- **Multi-locale build**: The Angular client ships two variants (English default + German `production-de`); `ng build --configuration production` for English, `ng build --configuration production-de` for German.

---

## Data Structures & Coordinate System

### Coordinate System (applies everywhere — critical to get right)

All coordinates — PCGTS polygon points, staff-line paths, symbol positions, and pattern-match bounding boxes — use the same **height-normalised** system:

```
x_stored = pixel_x / imageHeight
y_stored = pixel_y / imageHeight
```

Both axes are divided by the image **height** (not width). Consequences:
- `y` is always in `[0, 1]`.
- `x` is in `[0, imageWidth/imageHeight]` (typically `[0, ~0.7]` for portrait pages).
- This matches the Angular SVG overlay which is forced square via `aspect-ratio: 1/1; height: 100%`.
- The SVG `viewBox="0 0 1 1"` with `preserveAspectRatio="none"` stretches the square, so SVG x=0.5 always means "50% of image height from left".

The client multiplies stored values by `Constants.GLOBAL_SCALING = 1000` on load and divides back on save, giving an internal space of height=1000 and width=`(imageWidth/imageHeight)*1000`. The JSON wire format always uses the raw height-normalised floats.

### PCGTS JSON Structure

Endpoint: `GET /api/book/{book}/page/{page}/content/pcgts`
Server view: `restapi/views/pageaccess.py → PagePcGtsView`
Server model: `database/file_formats/pcgts/`
Client model: `src/app/data-types/page/`

```jsonc
{
  "version": 1,
  "meta": { "creator": "", "created": "<ISO>", "lastChange": "<ISO>" },
  "page": {
    "imageFilename": "color_norm.jpg",
    "imageWidth": 850,      // actual pixel width of the reference image
    "imageHeight": 1200,    // actual pixel height — used as the normalisation divisor
    "p_id": "<uuid>",
    "blocks": [
      {
        "id": "<block-id>",
        "type": "music",    // BlockType: "music" | "lyrics" | "paragraph" | "heading" | ...
        "coords": "x1,y1 x2,y2 x3,y3 x4,y4",  // height-normalised polygon (space-sep pairs)
        "lines": [
          {
            "id": "<line-id>",
            "coords": "x1,y1 x2,y2 ...",       // height-normalised bounding polygon
            "reconstructed": false,
            "documentStart": false,
            "staffLines": [
              {
                "id": "<sl-id>",
                "coords": "x1,y1 x2,y2 ...",   // height-normalised polyline path
                "highlighted": false,
                "space": false
              }
            ],
            "symbols": [
              {
                "id": "<sym-id>",
                "type": "note",   // "note" | "clef" | "accid"
                "coord": "x,y",   // height-normalised single point
                "positionInStaff": 5,
                "noteType": 0,
                "graphicalConnection": 0,  // 0=Gaped, 1=Looped, 2=NeumeStart
                "oct": 3,
                "pname": 2        // NoteName enum value
              }
            ],
            "sentence": { "syllables": [] }
          }
        ]
      }
    ],
    "readingOrder": { ... },
    "annotations": { ... },
    "comments": { ... }
  }
}
```

To extract music-line AABBs in height-normalised coordinates (as done in `PatternPdfExportService`):

```typescript
// Parse coords string → find min/max y values
const ys = line.coords.trim().split(/\s+/).map(pt => Number(pt.split(',')[1]));
const minY = Math.min(...ys);
const maxY = Math.max(...ys);
```

### Pattern Search Result Structure

Operation: `symbols_pattern_matcher`
Endpoint: `PUT /api/book/{book}/operation/symbols_pattern_matcher`
Server predictor: `omr/steps/tools/symbol_pattern_matching/predictor.py`
Client component: `src/app/search/symbol-pattern-search/`

**Request body:**
```json
{
  "selection": { "count": "All", "pages": [], "selected_pages_range_as_regex": "" },
  "params": {
    "patterns": [[0, 1, -1], [2, 0, -2]],
    "syllable_only": false
  }
}
```

Each sub-pattern entry is `[pitch_interval, connection_type]`; `connection_type` is `null` (any), `0` (Gaped), or `1` (Looped). The simpler integer-only format (connection ignored) is also accepted.

**Result payload** (under `res.result.results[]`):
```jsonc
{
  "page_id": "001",
  "total_count": 12,
  "matches": [
    {
      "line_id": "<line-id>",   // references a PageLine in PCGTS
      "pattern": [0, 1, -1],   // the matched pitch-interval sequence
      "count": 4,
      "boxes": [
        {
          "x": 0.12,   // left edge   — height-normalised
          "y": 0.31,   // top edge    — height-normalised
          "w": 0.08,   // width       — height-normalised
          "h": 0.06    // height      — height-normalised
        }
      ]
    }
  ]
}
```

Box padding is computed from `avg_staff_line_distance()`:
- x: half the gap to the adjacent note (clamped to `[staff_space*0.4, staff_space*1.5]`)
- y: `staff_space * 2.0` above and below

### Client-side key types

| Type | File | Role |
|------|------|------|
| `PageCommunication` | `data-types/communication.ts` | Builds all page-scoped API URLs |
| `BookCommunication` | `data-types/communication.ts` | Builds all book-scoped API URLs |
| `PcGts` | `data-types/page/pcgts.ts` | Top-level PCGTS container |
| `Page` | `data-types/page/page.ts` | Page with blocks; internal height=1000 |
| `Block` | `data-types/page/block.ts` | Region; `type: BlockType` |
| `PageLine` | `data-types/page/pageLine.ts` | Music or text line; `coords: PolyLine` |
| `PatternStyleConfig` | `search/symbol-pattern-search/pattern-style-config/` | Typed config for box/label colours |
| `PatternPdfExportService` | `search/symbol-pattern-search/pattern-pdf-export.service.ts` | Canvas-based PDF export |

`PageCommunication` URL helpers used in the search/export feature:

```typescript
pageCom.image_url('color', 'highres_preproc')  // → /api/book/{b}/page/{p}/content/color_highres_preproc
pageCom.content_url('pcgts')                   // → /api/book/{b}/page/{p}/content/pcgts
```

### Image resolutions

| Content key | Max width | Notes |
|---|---|---|
| `color_original` | original | raw scan, no preprocessing |
| `color_highres_preproc` | 2500 px | used by the editor and PDF export |
| `color_lowres_preproc` | 1250 px | used for previews |
| `color_norm` | variable | normalised to 10 px per staff-line distance |
| `color_norm_x2` | variable | 20 px per staff-line distance |

Server constant: `database/database_file.py` → `high_res_max_width = 2500`, `low_res_max_width = 1250`.
