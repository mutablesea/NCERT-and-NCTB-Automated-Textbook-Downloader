# NCERT & NCTB Automated Textbook Downloader

An automated Python tool (CLI & Desktop GUI) to browse, download, and organize official textbook PDFs from **NCERT (India)** and **NCTB (Bangladesh)**:

- **🇧🇩 NCTB (National Curriculum and Textbook Board — Bangladesh):** Supports downloading textbooks from **Academic Year 2017 to 2026** (including Higher Secondary `2025-2026` and `2026-2027`) across Pre-Primary, Primary, Secondary, Higher Secondary, Ibtedayi, Dakhil, Vocational, and Ethnic Minority streams.
- **🇮🇳 NCERT (National Council of Educational Research and Training — India):** Supports downloading English and Bengali version textbooks for **Classes 1–12** (General & Vocational Education portals).

All textbooks are organized automatically under **Academic Year** root folders with standardized stream and class hierarchies (`GC`, `IC`, `DC`, `VC`, `CC/GC/MC/SC/TC`).

---

## ⚙️ Features

1. **Desktop GUI & Interactive CLI:**
   - Includes a built-in **Tkinter GUI** ([download_books_gui.py](download_books_gui.py)) for searching, filtering, and selecting individual books, alongside dedicated CLI scripts for NCERT, NCTB, or combined downloads.
2. **NCERT ZIP Automation & Flattening:**
   - Downloads complete textbook ZIP packages (`https://ncert.nic.in/textbook/pdf/{code}dd.zip`), extracts chapter PDFs directly into clean book folders, flattens nested subdirectories, and removes temporary archives automatically.
   - Falls back to chapter-by-chapter PDF downloading if a full-book ZIP is unavailable.
3. **NCTB Dual-Engine Downloader & Web Fallback:**
   - **Primary Engine:** Direct high-speed streaming from Bangladesh e-Gov Cloud (`drive.egovcloud.gov.bd`).
   - **Secondary Engine:** Automatic Google Drive fallback with large-file confirmation token handling, plus optional web search fallback if an official link is broken.
4. **Resumable & Atomic Downloads:**
   - Streams active downloads into `.tmp` files and renames them atomically upon completion.
   - Automatically detects and skips previously downloaded books on re-runs.
5. **Zero External Dependencies:**
   - Runs out-of-the-box on **Python 3.7+** using only the standard library (`urllib`, `ssl`, `zipfile`, `concurrent.futures`, `tkinter`). No `pip install` required.

---

## 📊 Catalog & Approximate Storage Size

If you choose to download the entire catalog for an academic year, approximate disk usage is as follows:

| Portal / Category | Approx. Books | Approx. Size | Coverage |
| :--- | :---: | :---: | :--- |
| **🇮🇳 NCERT General (Classes 1–12)** | ~195 Books | ~12.7 GB | English & Bengali versions (`textbook.php`) |
| **🇮🇳 NCERT Vocational (Classes 9–12)** | ~76 Books | ~1.3 GB | Skill & trade textbooks (`vocational.php`) |
| **🇧🇩 NCTB Full Academic Year (e.g. 2026)** | ~511 Books | ~26.0 GB | General, Madrasah (Ibtedayi/Dakhil), Vocational, Higher Secondary & Ethnic Minority |

> [!TIP]
> You do not need to download everything at once. Use the GUI or CLI filters (`--source`, `--academic-year`, `--stages`, `--classes`) to download only the specific classes or books you need.

---

## 🚀 Usage (GUI & CLI)

### 1. Launch the Desktop GUI
```bash
python3 download_books_gui.py
```

### 2. Download NCERT Textbooks Only (`download_books_ncert.py`)
```bash
# Interactive mode (prompts for class numbers, Vocational option, and book selection)
python3 download_books_ncert.py

# Include NCERT Vocational Education portal (https://ncert.nic.in/vocational.php)
python3 download_books_ncert.py --include-vocational

# Non-interactive: download all NCERT General + Vocational books automatically
python3 download_books_ncert.py --non-interactive --include-vocational
```

### 3. Download NCTB Textbooks Only (`download_books_nctb.py`)
```bash
# Interactive mode (prompts for Academic Year, class numbers, and book selection)
python3 download_books_nctb.py

# Download a specific academic year (e.g. 2026, 2025, 2024)
python3 download_books_nctb.py --academic-year 2026

# Non-interactive: download all books for a specific academic year without prompts
python3 download_books_nctb.py --academic-year 2026 --non-interactive
```

### 4. Combined Downloader (`download_books.py` — NCERT + NCTB)
```bash
# Interactive mode
python3 download_books.py

# Non-interactive (Default): downloads NCTB default year + NCERT General (Classes 1–12)
python3 download_books.py --non-interactive

# Non-interactive (Full with NCERT Vocational)
python3 download_books.py --non-interactive --include-vocational

# Disable internet search fallback (use official portal links only)
python3 download_books.py --non-interactive --no-web-search
```

### 5. Filter by Specific Classes, Stages, or Custom Output Path
```bash
# Download specific classes only (e.g. Class 9 and 10)
python3 download_books.py --classes 9 10

# Download specific NCTB stages only
python3 download_books.py --source nctb --stages pre-primary primary ibtedayi --classes 1 2 3 4 5
python3 download_books.py --source nctb --stages higher-secondary
python3 download_books.py --source nctb --stages vocational --classes 10

# Exclude specific stages
python3 download_books.py --source nctb --exclude-stages pre-primary primary ibtedayi ethnic-minority

# Custom output directory and worker thread count
python3 download_books.py --output "./Textbooks" --workers 8

# Dry run (preview book list and target folder paths without downloading)
python3 download_books.py --dry-run
```

---

## 📂 Output Directory Structure

```text
NCERT & NCTB Books/
├── download_books.py                 # Combined CLI downloader (NCERT + NCTB)
├── download_books_ncert.py           # NCERT-only CLI downloader
├── download_books_nctb.py            # NCTB-only CLI downloader
├── download_books_gui.py             # Tkinter Desktop GUI downloader
├── README.md
│
├── NCERT/
│   └── Academic Year 2026-2027/
│       ├── 1. General Class-I/ .. 12. General Class-XII/
│       │   └── {Subject}-GC{n}/{Book}-GC{n}/{Book}-GC{n}-{Ch|Prelims}-AY26-27-{code}.pdf
│       └── 13. Vocational Education/
│           └── {9..12}. Vocational Class-{IX..XII}/
│               └── {Sector}-VC{n}/{Book}-VC{n}/{Book}-VC{n}-{Ch|Prelims}-AY26-27-{code}.pdf
│
└── NCTB/
    └── Academic Year 2026/
        ├── 1. Pre-Primary/
        ├── 2. Primary/
        ├── 3. Secondary/
        ├── 4. Higher Secondary/
        ├── 5. Ibtedayi/
        ├── 6. Dakhil/
        ├── 7. Vocational/
        └── 8. Ethnic Minority/
```

---

## 🔗 Official Sources

- **NCERT Textbooks Portal (Classes 1–12):** https://ncert.nic.in/textbook.php?ln=en
- **NCERT Vocational Education Portal:** https://ncert.nic.in/vocational.php
- **NCTB Official Portal (Bangladesh):** https://nctb.gov.bd
