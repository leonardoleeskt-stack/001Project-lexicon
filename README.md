# 001Project Personal Lexicon

Local tool: pick a small authorized folder → extract short words/proper nouns → you confirm → export a Microsoft Pinyin user-defined phrase `.dat`. Does not scan the whole disk, read external E:, auto-write the IME lexicon, or upload to the cloud. Windows + Microsoft Pinyin. Needs local Python (or the included Start.bat). v0.1 trial.

Chinese UI/docs: Chinese edition planned on Gitee (domestic).

## Safety boundaries

- **No** full-disk scan
- **No** reading the external `E:` drive
- **No** auto-write to the IME lexicon (you import the `.dat` yourself)
- **No** cloud upload
- Browse folders; confirm before export

## Features

- Double-click `Start.bat` to open the browser UI (no tkinter)
- Use **Browse…** to choose the glossary folder and output directory
- Sensitive / uncertain terms are held back until you confirm export

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

Personal / internal trial tool. Default paths are examples only — use **Browse…** to point at a small set of materials you authorize.
