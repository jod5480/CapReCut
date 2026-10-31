# CapRecut — CapCut Companion Plugin & Video Descrambler

An automated XOR video descrambler, recovery engine, and companion workflow tool designed specifically for **CapCut Desktop** and scrambled MP4/MOV files.

---

## 🔍 The Problem: Why CapCut Videos Get Scrambled

CapCut Desktop saves project drafts and cached clips in:
```text
%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft\
```

To protect cached combination media and imported assets from direct copying, CapCut frequently applies **single-byte XOR encryption** (commonly using keys like `0xB4` or `0xBE`) to the MP4 file header and repeating blocks.

When this happens:
- The files cannot be played outside of CapCut (VLC, Premiere, and Windows Media Player report them as corrupt).
- CapCut itself reports them as missing/unsupported if drafts are moved across directories or drives.

---

## ⚙️ How CapRecut Solves This

CapRecut integrates directly with CapCut's filesystem to auto-detect, fit patterns, and descramble files:

1. **Auto-Scan CapCut Drafts**:
   Inspects `%LOCALAPPDATA%\CapCut\...`, locates all draft projects, and checks each video file for XOR scrambling:
   ```bash
   python caprecut_capcut.py scan-capcut
   ```

2. **Auto-Repair a CapCut Draft**:
   Descrambles all corrupted media inside a specific CapCut draft:
   ```bash
   python caprecut_capcut.py repair-draft <draft_id>
   ```

3. **Background Watcher**:
   Runs quietly in the background, monitoring CapCut's drafts folder and automatically descrambling any newly added scrambled clips as you edit:
   ```bash
   python caprecut_capcut.py watch-capcut
   ```

4. **Drag & Drop Quick Repair**:
   Drag and drop any `.mp4` file directly onto `CapRecut-CapCut.bat`.

5. **In-Browser Web UI**:
   Open `CapRecut.html` in any browser to inspect XOR keys, waveforms, and preview repaired videos with 100% private client-side processing (zero server uploads).

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+ (standard library only; no extra `pip` packages required)
- Windows (CapCut Desktop)

### Usage

Run the interactive CLI:
```bash
python caprecut_capcut.py
```
Or use the batch launcher `CapRecut-CapCut.bat`.

---

## 🛠️ CLI Reference

| Command | Description |
| :--- | :--- |
| `scan-capcut` | Scans all local CapCut draft folders for scrambled files |
| `repair-draft <id>` | Repairs all scrambled media in a draft (e.g. `repair-draft 1030`) |
| `repair-file <file>` | Repairs a standalone video file |
| `watch-capcut` | Watches CapCut drafts folder in real-time and auto-repairs |

---

## 🔒 Privacy
All repairs are performed 100% locally on your machine. Neither the CLI nor `CapRecut.html` transmits any files or telemetry to external servers.
