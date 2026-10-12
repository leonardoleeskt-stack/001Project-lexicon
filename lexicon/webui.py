"""Stdlib-only local browser UI (http.server + webbrowser). No tkinter."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .mask import ClassifiedTerm
from .pipeline import DEFAULT_INPUT_HINT, DEFAULT_OUTPUT_DIR, export_bundle, process_paths

IMPORT_TIP = (
    "Import steps: Settings > Time & language > Language > Chinese options > "
    "Microsoft Pinyin > Lexicon and self-learning > User-defined phrases > "
    "Import UserDefinedPhrase.dat"
)

# Session state for the single local user
_STATE: Dict[str, Any] = {
    "source": DEFAULT_INPUT_HINT,
    "output": DEFAULT_OUTPUT_DIR,
    "candidates": [],  # list[dict]
    "held_count": 0,
    "held_back": [],  # ClassifiedTerm
    "last_message": "",
}


def _blocked(p: str) -> bool:
    u = (p or "").replace("/", "\\").upper()
    return u.startswith("E:\\") or u == "E:"


def _open_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def _candidates_to_json() -> List[dict]:
    return list(_STATE["candidates"])


def browse_folder(initial: str = "") -> Optional[str]:
    """Pop a native Windows folder picker; return absolute path or None if cancelled.

    Uses PowerShell FolderBrowserDialog (no tkinter). On non-Windows returns None.
    """
    if sys.platform != "win32":
        return None

    init = (initial or "").strip()
    # Keep only existing dirs as SelectedPath; otherwise leave default.
    if init and not Path(init).is_dir():
        # Try parent if user typed a file-like path
        parent = str(Path(init).parent)
        init = parent if Path(parent).is_dir() else ""

    # Escape for PowerShell single-quoted string (double single-quotes).
    def _ps_quote(s: str) -> str:
        return "'" + s.replace("'", "''") + "'"

    ps_lines = [
        "Add-Type -AssemblyName System.Windows.Forms",
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog",
        "$d.Description = 'Select folder'",
        "$d.ShowNewFolderButton = $true",
    ]
    if init:
        ps_lines.append(f"$d.SelectedPath = {_ps_quote(init)}")
    ps_lines.extend(
        [
            "if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {",
            "  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8",
            "  Write-Output $d.SelectedPath",
            "}",
        ]
    )
    ps = "\n".join(ps_lines)
    try:
        # CREATE_NO_WINDOW would hide the dialog; use normal window so picker shows.
        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            # Still show UI: FolderBrowserDialog needs a message loop; do NOT hide console
            # of the dialog itself — only avoid flashing an extra console if possible.
            # Use STARTUPINFO to hide the PowerShell console window while dialog shows.
            pass
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE — hide PowerShell console, dialog still visible
        proc = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-STA",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            startupinfo=si,
        )
    except Exception:
        return None

    out = (proc.stdout or "").strip()
    if not out:
        return None
    # First non-empty line is the path
    chosen = out.splitlines()[0].strip()
    if not chosen:
        return None
    if _blocked(chosen):
        return None
    return str(Path(chosen))


def _do_browse(which: str, initial: str = "") -> dict:
    """API helper: which is 'source' or 'output'."""
    which = (which or "").strip().lower()
    if which not in ("source", "output"):
        return {"ok": False, "cancelled": True, "error": "unknown which"}
    start = (initial or "").strip()
    if not start:
        start = str(_STATE.get(which) or "")
    if sys.platform != "win32":
        return {
            "ok": False,
            "cancelled": True,
            "error": "Folder browse is only available on Windows; paste the path manually.",
        }
    path = browse_folder(start)
    if path is None:
        return {"ok": False, "cancelled": True}
    if _blocked(path):
        return {"ok": False, "cancelled": True, "error": "Selecting the E: drive is not allowed."}
    _STATE[which] = path
    return {"ok": True, "path": path, "which": which}


def _do_scan(source: str) -> dict:
    if not source.strip():
        return {"ok": False, "error": "Please enter a glossary folder path."}
    if _blocked(source):
        return {"ok": False, "error": "Scanning the E: drive is not allowed."}
    try:
        cands, held = process_paths([source.strip()])
    except Exception as e:
        return {"ok": False, "error": str(e)}

    _STATE["source"] = source.strip()
    _STATE["held_back"] = held
    _STATE["held_count"] = len(held)
    _STATE["candidates"] = [
        {"text": c.text, "pinyin": c.pinyin, "selected": True, "source": c.source}
        for c in cands
    ]
    _STATE["last_message"] = (
        f"Scan done: {len(cands)} candidate(s), {len(held)} held back. Review, then click Confirm export."
    )
    return {
        "ok": True,
        "candidates": _candidates_to_json(),
        "held_count": len(held),
        "message": _STATE["last_message"],
    }


def _do_export(output: str, selected_flags: List[bool]) -> dict:
    cands_data = _STATE["candidates"]
    if not cands_data and not _STATE["held_back"]:
        return {"ok": False, "error": "Please click Scan first."}
    out = (output or DEFAULT_OUTPUT_DIR).strip()
    if _blocked(out):
        return {"ok": False, "error": "Output directory cannot be the E: drive."}

    terms: List[ClassifiedTerm] = []
    for i, row in enumerate(cands_data):
        sel = selected_flags[i] if i < len(selected_flags) else bool(row.get("selected", True))
        terms.append(
            ClassifiedTerm(
                text=row["text"],
                pinyin=row.get("pinyin") or "",
                sensitive=False,
                reason="",
                source=row.get("source") or "",
                selected=sel,
            )
        )
        row["selected"] = sel

    _STATE["output"] = out
    try:
        result = export_bundle(terms, _STATE["held_back"], out, include_dat=True)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    _open_dir(Path(result["output_dir"]))
    msg = (
        f"Exported: {result['candidate_count']} candidate(s), {result['dat_count']} in .dat\n"
        f"Folder: {result['output_dir']}\n\n{IMPORT_TIP}"
    )
    _STATE["last_message"] = msg
    return {
        "ok": True,
        "message": msg,
        "output_dir": result["output_dir"],
        "dat_count": result["dat_count"],
    }


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>001Project Personal Lexicon</title>
<style>
  :root { font-family: "Segoe UI", "Microsoft YaHei", sans-serif; }
  body { max-width: 820px; margin: 24px auto; padding: 0 16px; color: #222; }
  h1 { font-size: 1.5rem; margin: 0 0 16px; }
  label { display: block; font-size: 0.9rem; margin-top: 10px; color: #444; }
  input[type=text] { width: 100%; box-sizing: border-box; padding: 8px 10px;
                     font-size: 0.95rem; margin-top: 4px; }
  .row { display: flex; gap: 8px; align-items: flex-end; }
  .row > div { flex: 1; min-width: 0; }
  .row .browse-wrap { flex: 0 0 auto; padding-bottom: 1px; }
  button.browse { padding: 8px 14px; font-size: 0.95rem; cursor: pointer;
                  margin-top: 4px; background: #f1f3f4; color: #222;
                  border: 1px solid #dadce0; border-radius: 6px; white-space: nowrap; }
  button.browse:hover { background: #e8eaed; }
  button.browse:disabled { opacity: 0.5; cursor: wait; }
  button.big { width: 100%; padding: 14px; font-size: 1.1rem; font-weight: 700;
               margin-top: 14px; cursor: pointer; background: #1a73e8; color: #fff;
               border: none; border-radius: 8px; }
  button.big:hover { background: #1557b0; }
  button.big.secondary { background: #0d9f4f; }
  button.big.secondary:hover { background: #0b7a3c; }
  button.big:disabled { opacity: 0.5; cursor: wait; }
  #held { margin: 10px 0 4px; color: #666; }
  #status { margin: 10px 0; padding: 10px; background: #f5f7fa; border-radius: 6px;
            white-space: pre-wrap; min-height: 1.2em; }
  #list { border: 1px solid #ddd; border-radius: 8px; max-height: 340px;
          overflow: auto; margin-top: 8px; }
  #list table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
  #list th, #list td { padding: 6px 8px; text-align: left; border-bottom: 1px solid #eee; }
  #list th { background: #fafafa; position: sticky; top: 0; }
  .err { color: #c62828; }
  .ok { color: #2e7d32; }
  .hint { font-size: 0.85rem; color: #888; margin-top: 16px; }
</style>
</head>
<body>
  <h1>001Project Personal Lexicon</h1>

  <div class="row">
    <div>
      <label>Glossary folder</label>
      <input type="text" id="source" value="__SOURCE__"/>
    </div>
    <div class="browse-wrap">
      <button type="button" class="browse" id="btnBrowseSource"
              onclick="doBrowse('source')">Browse…</button>
    </div>
  </div>
  <div class="row">
    <div>
      <label>Output folder</label>
      <input type="text" id="output" value="__OUTPUT__"/>
    </div>
    <div class="browse-wrap">
      <button type="button" class="browse" id="btnBrowseOutput"
              onclick="doBrowse('output')">Browse…</button>
    </div>
  </div>

  <button class="big" id="btnScan" onclick="doScan()">Scan</button>
  <div id="held">Held back: not scanned yet</div>
  <div id="list">
    <table>
      <thead><tr><th style="width:48px">Sel</th><th>Term</th><th>Pinyin</th></tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
  <button class="big secondary" id="btnExport" onclick="doExport()">Confirm export</button>
  <div id="status">Ready: click Scan to begin</div>
  <p class="hint">Local tool · no full-disk scan · no E: · no IME lex write · no cloud upload<br/>
  Import: Settings &gt; Time &amp; language &gt; Language &gt; Chinese options &gt; Microsoft Pinyin &gt; Lexicon and self-learning &gt; User-defined phrases &gt; Import</p>

<script>
async function api(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body || {})
  });
  return r.json();
}

function renderCandidates(rows) {
  const tb = document.getElementById('tbody');
  tb.innerHTML = '';
  (rows || []).forEach((row, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td><input type="checkbox" data-i="${i}" ${row.selected ? 'checked' : ''}/></td>
      <td>${escapeHtml(row.text)}</td>
      <td>${escapeHtml(row.pinyin || '')}</td>`;
    tb.appendChild(tr);
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

async function doBrowse(which) {
  const inputId = which === 'output' ? 'output' : 'source';
  const btnId = which === 'output' ? 'btnBrowseOutput' : 'btnBrowseSource';
  const btn = document.getElementById(btnId);
  const st = document.getElementById('status');
  const input = document.getElementById(inputId);
  btn.disabled = true;
  st.className = '';
  st.textContent = 'Please choose a folder in the dialog…';
  try {
    const data = await api('/api/browse', {
      which: which,
      initial: input.value
    });
    if (data.ok && data.path) {
      input.value = data.path;
      st.className = 'ok';
      st.textContent = 'Selected: ' + data.path;
      return;
    }
    if (data.cancelled) {
      st.className = '';
      st.textContent = data.error || 'Selection cancelled';
      return;
    }
    st.className = 'err';
    st.textContent = data.error || 'Browse failed';
  } catch (e) {
    st.className = 'err';
    st.textContent = 'Request failed: ' + e;
  } finally {
    btn.disabled = false;
  }
}

async function doScan() {
  const btn = document.getElementById('btnScan');
  const st = document.getElementById('status');
  btn.disabled = true;
  st.className = '';
  st.textContent = 'Scanning…';
  try {
    const data = await api('/api/scan', { source: document.getElementById('source').value });
    if (!data.ok) {
      st.className = 'err';
      st.textContent = data.error || 'Scan failed';
      return;
    }
    renderCandidates(data.candidates);
    document.getElementById('held').textContent =
      'Held back (sensitive / needs review, not exported): ' + data.held_count;
    st.className = 'ok';
    st.textContent = data.message;
  } catch (e) {
    st.className = 'err';
    st.textContent = 'Request failed: ' + e;
  } finally {
    btn.disabled = false;
  }
}

async function doExport() {
  const btn = document.getElementById('btnExport');
  const st = document.getElementById('status');
  const boxes = [...document.querySelectorAll('#tbody input[type=checkbox]')];
  const selected = boxes.map(b => b.checked);
  btn.disabled = true;
  st.className = '';
  st.textContent = 'Exporting…';
  try {
    const data = await api('/api/export', {
      output: document.getElementById('output').value,
      selected: selected
    });
    if (!data.ok) {
      st.className = 'err';
      st.textContent = data.error || 'Export failed';
      return;
    }
    st.className = 'ok';
    st.textContent = data.message;
  } catch (e) {
    st.className = 'err';
    st.textContent = 'Request failed: ' + e;
  } finally {
    btn.disabled = false;
  }
}
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quieter
        sys.stderr.write("[webui] " + (fmt % args) + "\n")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            html = (
                HTML_PAGE.replace("__SOURCE__", _escape_attr(_STATE["source"]))
                .replace("__OUTPUT__", _escape_attr(_STATE["output"]))
            )
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/state":
            self._json(
                200,
                {
                    "source": _STATE["source"],
                    "output": _STATE["output"],
                    "candidates": _candidates_to_json(),
                    "held_count": _STATE["held_count"],
                    "message": _STATE["last_message"],
                },
            )
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        data = self._read_json()
        if path == "/api/scan":
            self._json(200, _do_scan(str(data.get("source") or "")))
            return
        if path == "/api/export":
            selected = data.get("selected") or []
            flags = [bool(x) for x in selected]
            self._json(
                200,
                _do_export(str(data.get("output") or ""), flags),
            )
            return
        if path == "/api/browse":
            self._json(
                200,
                _do_browse(
                    str(data.get("which") or ""),
                    str(data.get("initial") or ""),
                ),
            )
            return
        self._json(404, {"ok": False, "error": "not found"})


def _escape_attr(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
    )


def _pick_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main(port: Optional[int] = None) -> None:
    """Start local server and open the default browser."""
    host = "127.0.0.1"
    port = port or _pick_port()
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"001Project web UI: {url}")
    print("Close this window to stop the server.")

    def _open() -> None:
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"Please open manually: {url} ({e})")

    threading.Timer(0.4, _open).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
