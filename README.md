# Seller Dispute Resolution System

A web application that helps resolve seller disputes by comparing product photos using AI/image similarity, generating compensation recommendations, and allowing human reviewers to make final decisions.

---

## What This App Does

When a seller raises a dispute (e.g., "wrong product received", "item damaged"), this system:
1. Imports dispute data from an Excel file
2. Downloads photos — seller photo, product listing photo (PDP), and quality check photo (DSQC)
3. Compares the photos using image similarity algorithms
4. Recommends a compensation percentage using rules or OpenAI
5. Lets a human reviewer approve, override, or reject the recommendation

---

## Project Structure

```
assignment_salphan/
│
├── .env                        # Your secret config (DB URL, API keys) — never share this
├── .env.example                # Template showing what goes in .env
├── requirements.txt            # Python libraries this project needs
├── SHD_Dispute_data.xlsx       # Sample Excel file with dispute data
│
├── frontend/                   # The webpage (what users see in browser)
│   ├── index.html              # Page structure — buttons, sections, layout
│   ├── styles.css              # Visual styling — colors, fonts, spacing
│   └── app.js                  # Frontend logic — calls backend API, updates page
│
├── backend/
│   └── app/
│       ├── main.py             # Entry point — starts server, connects everything
│       ├── config.py           # Reads .env settings and makes them available
│       ├── database.py         # Connects to PostgreSQL (Neon), manages sessions
│       ├── models.py           # Defines DB table structures (Dispute, Image, etc.)
│       ├── init_db.py          # One-time script to create DB tables
│       │
│       ├── excel_parser.py     # Reads uploaded Excel, extracts dispute rows + image URLs
│       ├── dispute_service.py  # Saves parsed Excel data into the database
│       │
│       ├── image_downloader.py # Downloads images from URLs (handles Google Drive, SharePoint)
│       ├── image_service.py    # Coordinates image downloading per dispute
│       │
│       ├── similarity.py       # Compares two images using color histogram (OpenCV)
│       ├── analysis_service.py # Builds analysis result — mock rules or OpenAI GPT-4o
│       ├── analysis_pipeline.py# Orchestrates full analysis + saves result to DB
│       │
│       └── routers/
│           └── disputes.py     # All API endpoints (URLs the frontend calls)
│
└── storage/                    # Downloaded images saved here, organized by transaction ID
    └── {transaction_id}/
        ├── seller/             # Photos sent by seller
        ├── pdp/                # Product listing photos (catalog)
        └── dsqc/               # Quality check photos (pickup scan)
```

---

## Database Tables

```
disputes            — One row per dispute (transaction ID, seller, product, status)
dispute_images      — Image URLs and local file paths linked to a dispute
analysis_results    — AI/similarity scores and compensation recommendation
human_reviews       — Final human decision (approved / overridden / rejected)
```

---

## Setup & Running

### Prerequisites
- Python 3.11+
- Virtual environment already set up (`.venv` folder exists)
- `.env` file configured (copy from `.env.example` and fill in `DATABASE_URL`)

### Step 1 — Activate the virtual environment

```zsh
cd /Users/supriyadebnath/Projects/assignment_salphan
source .venv/bin/activate
```

> You'll see `(.venv)` in your terminal. This means Python is using this project's libraries.

### Step 2 — Install dependencies (first time only)

```zsh
pip install -r requirements.txt
```

### Step 3 — Start the backend server

```zsh
uvicorn backend.app.main:app --reload --port 8000
```

> `--reload` means the server auto-restarts when you edit code. Good for development.

### Step 4 — Initialize the database (first time only)

Open your browser and go to:
```
http://localhost:8000/api/db/init
```
Or run in terminal:
```zsh
curl -X POST http://localhost:8000/api/db/init
```

### Step 5 — Open the app

```
http://localhost:8000/ui
```

### Health Check

To verify the server and database are working:
```
http://localhost:8000/health
```
Returns: server status, database connection status, active AI provider.

### API Docs (auto-generated)

```
http://localhost:8000/docs
```

---

## Environment Variables (`.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Neon PostgreSQL connection string | `postgresql://user:pass@host/db` |
| `STORAGE_PATH` | Where to save downloaded images | `storage` |
| `AI_PROVIDER` | `mock` (rules-based) or `openai` | `mock` |
| `OPENAI_API_KEY` | Required only if `AI_PROVIDER=openai` | `sk-...` |

---

## API Endpoints

| Method | URL | What it does |
|--------|-----|-------------|
| `GET` | `/health` | Check server + DB status |
| `POST` | `/api/db/init` | Create DB tables (run once) |
| `POST` | `/api/disputes/upload` | Upload Excel file |
| `GET` | `/api/disputes` | List all disputes |
| `GET` | `/api/disputes/{id}` | Get one dispute with images + analysis |
| `POST` | `/api/disputes/{id}/download-images` | Download images for one dispute |
| `POST` | `/api/disputes/{id}/analyze` | Run AI analysis for one dispute |
| `POST` | `/api/disputes/{id}/review` | Submit human review decision |
| `POST` | `/api/disputes/download-all` | Download images for all disputes |
| `POST` | `/api/disputes/analyze-all` | Analyze all disputes |

---

## Full Application Flow Diagram

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                        SELLER DISPUTE RESOLUTION — FULL FLOW                    ║
╚══════════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────────┐
│  STARTUP                                                                        │
│                                                                                 │
│  Terminal                                                                       │
│  ──────────────────────────────────────────────────────────────────────────    │
│  1. source .venv/bin/activate   → activates Python environment                 │
│  2. pip install -r requirements.txt  → installs FastAPI, OpenCV, SQLAlchemy    │
│  3. uvicorn backend.app.main:app --reload --port 8000                          │
│         │                                                                       │
│         ▼                                                                       │
│     main.py runs                                                                │
│         │                                                                       │
│         ├── config.py reads .env  →  loads DATABASE_URL, AI_PROVIDER, etc.    │
│         ├── CORS middleware added  →  allows browser to call the API           │
│         ├── /files route mounted  →  serves images from storage/ folder        │
│         ├── /ui route mounted     →  serves frontend/ folder as webpage        │
│         └── /api/disputes router  →  all dispute API endpoints registered      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  DATABASE INIT (one-time)                                                       │
│                                                                                 │
│  POST /api/db/init                                                              │
│         │                                                                       │
│         ▼                                                                       │
│     database.py                                                                 │
│         ├── get_engine()  →  creates SQLAlchemy engine using DATABASE_URL      │
│         └── create_tables()                                                     │
│                  │                                                              │
│                  ▼                                                              │
│             models.py defines 4 tables:                                        │
│             ┌──────────────────┐  ┌──────────────────┐                        │
│             │    disputes      │  │  dispute_images   │                        │
│             │──────────────────│  │──────────────────│                        │
│             │ id               │  │ id               │                        │
│             │ transaction_id   │  │ dispute_id (FK)  │                        │
│             │ seller_name      │  │ image_type       │                        │
│             │ product_name     │  │ source_url       │                        │
│             │ dispute_reason   │  │ file_path        │                        │
│             │ product_cost_inr │  └──────────────────┘                        │
│             │ status           │                                               │
│             └──────────────────┘                                               │
│             ┌──────────────────┐  ┌──────────────────┐                        │
│             │ analysis_results │  │  human_reviews   │                        │
│             │──────────────────│  │──────────────────│                        │
│             │ id               │  │ id               │                        │
│             │ dispute_id (FK)  │  │ dispute_id (FK)  │                        │
│             │ provider         │  │ decision         │                        │
│             │ similarity_scores│  │ compensation_pct │                        │
│             │ result_json      │  │ notes            │                        │
│             │ recommended_pct  │  └──────────────────┘                        │
│             └──────────────────┘                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STEP 1 — UPLOAD EXCEL                                                          │
│                                                                                 │
│  Browser: User uploads SHD_Dispute_data.xlsx                                   │
│         │                                                                       │
│         ▼                                                                       │
│  POST /api/disputes/upload   (routers/disputes.py)                             │
│         │                                                                       │
│         ▼                                                                       │
│  excel_parser.py — parse_excel(file_bytes)                                     │
│         ├── Opens .xlsx as ZIP archive                                         │
│         ├── Reads sharedStrings.xml  →  resolves cell text values             │
│         ├── Reads sheet1.xml row by row                                        │
│         │    Column A → transaction_id                                         │
│         │    Column B → seller_name                                            │
│         │    Column C → product_name                                           │
│         │    Column D → dispute_reason                                         │
│         │    Column E → seller image URLs                                      │
│         │    Column F → PDP image URLs                                         │
│         │    Column G → DSQC image URLs                                        │
│         ├── split_urls()  →  extracts multiple URLs from a single cell        │
│         └── normalize_url()  →  fixes missing https://, strips whitespace     │
│                  │                                                              │
│                  ▼                                                              │
│  dispute_service.py — import_disputes(db, rows)                                │
│         ├── For each row: check if transaction_id already exists in DB        │
│         │    ├── New  →  INSERT into disputes table                           │
│         │    └── Existing  →  UPDATE existing row                             │
│         ├── Delete old images for this dispute                                 │
│         └── INSERT each image URL into dispute_images table                   │
│                  │                                                              │
│                  ▼                                                              │
│  Response: { imported: N, updated: M, total_rows: X, errors: [] }             │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STEP 2 — LIST DISPUTES                                                         │
│                                                                                 │
│  Browser: Dispute list loads automatically                                     │
│         │                                                                       │
│         ▼                                                                       │
│  GET /api/disputes   (routers/disputes.py)                                     │
│         │                                                                       │
│         ▼                                                                       │
│  Query disputes table  →  returns transaction_id, seller, product,            │
│                            dispute_reason, status, image_count                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STEP 3 — DOWNLOAD IMAGES                                                       │
│                                                                                 │
│  Browser: User clicks "Download Images" for a dispute                          │
│         │                                                                       │
│         ▼                                                                       │
│  POST /api/disputes/{transaction_id}/download-images                           │
│         │                                                                       │
│         ▼                                                                       │
│  image_service.py — download_dispute_images(db, dispute)                       │
│         │                                                                       │
│         ├── For each image in dispute_images table:                            │
│         │    ├── Skip if already downloaded (file_path exists)                │
│         │    └── Call image_downloader.py — download_source(url, dir, prefix) │
│         │                                                                       │
│         └── image_downloader.py                                                │
│              ├── normalize_url()                                               │
│              │    ├── Google Drive URL?  →  rewrite to direct download link   │
│              │    └── SharePoint URL?   →  add ?download=1 param              │
│              ├── Fetch URL with HTTP request (User-Agent header set)          │
│              │    ├── Direct image URL (.jpg/.png)?  →  save directly         │
│              │    └── HTML page?  →  parse page, find <img> tags, download   │
│              └── write_bytes()  →  saves file to:                             │
│                   storage/{transaction_id}/{image_type}/{prefix}.jpg          │
│                                                                                 │
│  Updates dispute_images.file_path in DB                                        │
│  Updates dispute.status = "images_downloaded"                                  │
│                                                                                 │
│  Saved folder structure:                                                        │
│  storage/                                                                       │
│  └── 100114057336388/                                                           │
│       ├── seller/   seller_20_1.jpg                                            │
│       ├── pdp/      pdp_21.jpeg                                                │
│       └── dsqc/     dsqc_33_1.jpg, dsqc_33_2.jpg ...                         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STEP 4 — RUN ANALYSIS                                                          │
│                                                                                 │
│  Browser: User clicks "Run Analysis"                                           │
│         │                                                                       │
│         ▼                                                                       │
│  POST /api/disputes/{transaction_id}/analyze                                   │
│         │                                                                       │
│         ▼                                                                       │
│  analysis_pipeline.py — analyze_dispute(db, dispute)                           │
│         │                                                                       │
│         ├── _images_by_type()  →  groups local file paths by type             │
│         │    { pdp: [...], dsqc: [...], seller: [...] }                        │
│         │                                                                       │
│         ├── similarity.py — compute_similarity_scores(images_by_type)         │
│         │    ├── Loads each image with OpenCV, resizes to 256×256             │
│         │    ├── Computes 3D color histogram for each image                   │
│         │    ├── Compares histograms using HISTCMP_CORREL (0.0 to 1.0)       │
│         │    └── Returns 3 scores:                                             │
│         │         pdp_vs_dsqc   (catalog vs quality check)                    │
│         │         dsqc_vs_seller (quality check vs seller photo)              │
│         │         pdp_vs_seller  (catalog vs seller photo)  ← most important  │
│         │                                                                       │
│         └── analysis_service.py — builds the result                           │
│              │                                                                  │
│              ├── AI_PROVIDER = "mock"  →  analyze_with_mock()                 │
│              │    └── _compensation_pct() — rules engine:                     │
│              │         "wrong product" or pdp_vs_seller < 0.35  →  100%      │
│              │         "empty box" / "missing"                  →  100%      │
│              │         "damaged" + avg score >= 0.5             →   25%      │
│              │         "damaged" + avg score <  0.5             →  100%      │
│              │         "used"    + avg score <  0.55            →  100%      │
│              │         default   + avg score >= 0.5             →   30%      │
│              │                                                                  │
│              └── AI_PROVIDER = "openai"  →  analyze_with_openai()            │
│                   ├── Encodes images as base64                                 │
│                   ├── Sends to GPT-4o-mini with dispute context               │
│                   ├── Gets structured JSON back                                │
│                   └── Falls back to mock if OpenAI fails                      │
│                                                                                 │
│  Saves AnalysisResult to DB                                                    │
│  Updates dispute.status = "analyzed"                                           │
│                                                                                 │
│  Result includes:                                                               │
│  ├── similarity_scores  { pdp_vs_seller: 0.72, ... }                          │
│  ├── product_match      { same_product: true, confidence: 0.72 }              │
│  ├── observations       { visible_damage, packaging, condition }               │
│  ├── dispute_validation { claimed_reason, validated, severity }               │
│  └── compensation       { recommended_pct: 25, amount_inr: 1250 }            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STEP 5 — HUMAN REVIEW                                                          │
│                                                                                 │
│  Browser: Reviewer sees AI recommendation, fills in review form               │
│         │                                                                       │
│         ▼                                                                       │
│  POST /api/disputes/{transaction_id}/review                                    │
│  Body: { decision: "approved", final_compensation_pct: 25, notes: "..." }     │
│         │                                                                       │
│         ▼                                                                       │
│  analysis_pipeline.py — save_human_review()                                    │
│         ├── Creates or updates HumanReview row in DB                          │
│         │    decision: "approved" | "overridden" | "rejected"                 │
│         │    final_compensation_pct: reviewer's chosen %                      │
│         │    notes: free text                                                  │
│         └── Updates dispute.status = "reviewed"                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  DISPUTE STATUS LIFECYCLE                                                       │
│                                                                                 │
│  pending  →  images_downloaded  →  analyzed  →  reviewed                      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘


╔══════════════════════════════════════════════════════════════════════════════════╗
║                         COMPONENT INTERACTION MAP                               ║
╚══════════════════════════════════════════════════════════════════════════════════╝

  Browser (frontend/)
  ┌─────────────────────────────────────────────────────┐
  │  index.html  ←  structure                           │
  │  styles.css  ←  appearance                          │
  │  app.js      ←  calls API, renders results          │
  └──────────────────────┬──────────────────────────────┘
                         │  HTTP requests
                         ▼
  FastAPI Server (backend/app/)
  ┌─────────────────────────────────────────────────────┐
  │  main.py  ←  starts everything                      │
  │  routers/disputes.py  ←  handles all /api/ URLs     │
  │       │                                             │
  │       ├── excel_parser.py                          │
  │       ├── dispute_service.py                       │
  │       ├── image_service.py                         │
  │       │       └── image_downloader.py              │
  │       ├── analysis_pipeline.py                     │
  │       │       ├── similarity.py  (OpenCV)          │
  │       │       └── analysis_service.py              │
  │       │               └── OpenAI API (optional)    │
  │       └── database.py  ←  DB sessions              │
  └──────────────────────┬──────────────────────────────┘
                         │  SQLAlchemy ORM
                         ▼
  Neon PostgreSQL (cloud database)
  ┌─────────────────────────────────────────────────────┐
  │  disputes          │  dispute_images                │
  │  analysis_results  │  human_reviews                 │
  └─────────────────────────────────────────────────────┘

  Local Disk
  ┌─────────────────────────────────────────────────────┐
  │  storage/{transaction_id}/seller/  *.jpg            │
  │  storage/{transaction_id}/pdp/     *.jpeg           │
  │  storage/{transaction_id}/dsqc/    *.jpg            │
  └─────────────────────────────────────────────────────┘
```

---

## AI Provider Modes

| Mode | How it works | When to use |
|------|-------------|-------------|
| `mock` | Rules-based logic using similarity scores + dispute reason keywords | Default, no API key needed |
| `openai` | Sends images + context to GPT-4o-mini, gets structured JSON verdict | Set `AI_PROVIDER=openai` and add `OPENAI_API_KEY` in `.env` |

If OpenAI fails for any reason, it automatically falls back to mock mode.

---

## Similarity Score Explained

The app compares images using **color histogram correlation** (OpenCV):
- Score of `1.0` = images look identical
- Score of `0.0` = images look completely different
- Score below `0.35` on `pdp_vs_seller` = likely wrong product → 100% compensation

Three comparisons are made per dispute:
- `pdp_vs_dsqc` — catalog photo vs quality check photo
- `dsqc_vs_seller` — quality check photo vs seller's received photo
- `pdp_vs_seller` — catalog photo vs seller's received photo *(most important)*
