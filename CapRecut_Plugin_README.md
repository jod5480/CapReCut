# CapRecut — CapCut Companion Plugin & Video Descrambler

## Why CapCut Videos Get Scrambled
CapCut Desktop saves project drafts in `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft\`. To protect cached combination media and imported assets from direct copying, CapCut frequently applies **single-byte XOR encryption** (commonly using keys like `0xB4` or `0xBE`) to the MP4 file header and repeating blocks. 

When this happens, the files cannot be played outside of CapCut or report as corrupted/unsupported inside CapCut when drafts are relocated.

## Can This Be Installed Directly *Inside* CapCut?
**No.** CapCut (desktop, web, and mobile) is a closed proprietary application developed by ByteDance. It **does not have a native plugin API, extension directory, or plugin marketplace** (unlike Adobe Premiere CEP/UXP or DaVinci Resolve OpenFX).

## How CapRecut Solves This (The External Workflow Plugin)
CapRecut integrates directly with CapCut's Windows draft filesystem:

1. **Auto-Scan CapCut Drafts**:
   Automatically inspects `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`, locates all draft projects, and checks each video file for XOR scrambling.
   ```bash
   python caprecut_capcut.py scan-capcut
   ```

2. **Auto-Repair a CapCut Draft**:
   Descrambles all corrupted media inside a specific CapCut draft (or all drafts):
   ```bash
   python caprecut_capcut.py repair-draft 1030
   ```

3. **Background Watcher**:
   Runs quietly in the background, monitoring CapCut's drafts folder and automatically descrambling any newly added scrambled clips as you edit:
   ```bash
   python caprecut_capcut.py watch-capcut
   ```

4. **Drag & Drop Quick Repair**:
   Drag and drop any `.mp4` file directly onto `CapRecut-CapCut.bat`.

5. **Web Interface**:
   Open `CapRecut.html` in any browser to inspect XOR keys, waveforms, and preview repaired videos with zero server uploads.

