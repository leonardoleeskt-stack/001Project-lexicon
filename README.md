# 001Project Personal Lexicon

**One folder of terms → one Microsoft Pinyin `.dat`. Local only. Works offline. No ads.**

Pick a small folder you authorize → scan short words / proper nouns → you confirm → export `UserDefinedPhrase.dat` for Microsoft Pinyin. No cloud, no full-disk scan, no silent IME writes. Windows only. **v0.1 trial.**

<!-- SCREENSHOT_OR_GIF: place a 10–20s GIF or still here
     Suggested frames: (1) Start.bat → browser UI (2) Browse… picks a folder
     (3) Scan list with held-back rows (4) Confirm export → .dat on disk
     Do NOT show real client docs, company logos, faces, or price sheets.
     Use repo `sample/` only. -->

### 30-second start

1. Clone / unzip → double-click `Start.bat` (Python 3.10+ on PATH, or a venv the script finds).
2. **Browse…** → pick a small glossary folder → **Scan**.
3. Review candidates (sensitive / uncertain rows stay held back) → **Confirm export**.
4. Windows Settings → Time & language → Language → Chinese → Microsoft Pinyin → Lexicon and self-learning → User-defined phrases → **Import** the `.dat`.

Chinese docs / domestic mirror: Gitee edition in progress (link TBD).

## Safety boundaries

- **No** full-disk scan
- **No** reading external drives you did not pick (including a wholesale `E:` crawl)
- **No** auto-write to the IME system lexicon — you import the `.dat` yourself
- **No** cloud upload
- Browse a folder; confirm before export

## Features

- Double-click `Start.bat` to open the browser UI (no tkinter)
- **Browse…** for glossary folder and output directory
- Sensitive / uncertain terms held back until you confirm export
- Works fully offline; no ads

## Usage (Windows)

1. Double-click `Start.bat` (needs Python 3.10+ on PATH, or an existing venv the script can find)
2. Pick a glossary folder → **Scan** → review candidates → **Confirm export**
3. Settings → Time & language → Language → Chinese options → Microsoft Pinyin → Lexicon and self-learning → User-defined phrases → **Import** `UserDefinedPhrase.dat`
4. On failure, check `launch-error.log` in the same folder

(`一键生成.bat` is a compatibility alias that calls `Start.bat`.)

## Self-test

```bash
python run.py selftest
```

## Dependencies

- Python 3.10+
- `pypinyin` (a wheel is included under `vendor/`; the start script can install offline)

## License & scope

MIT — see [`LICENSE`](./LICENSE). Personal / trial tool, not a store-grade product. Default paths in docs are examples only; use **Browse…** on a small set of materials you authorize. Keep real client data out of public forks.
