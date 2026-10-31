#!/usr/bin/env python3
"""
CapRecut — CapCut Companion Plugin & Video Descrambler
======================================================
Automated XOR video descrambler and draft recovery tool designed specifically for CapCut.

CapCut stores draft combination clips, cache, and project resources in:
  %LOCALAPPDATA%\\CapCut\\User Data\\Projects\\com.lveditor.draft\\<project_id>\\

This tool automatically detects XOR-scrambled MP4/MOV files inside CapCut drafts
or standalone video files, estimates repetition periods, and recovers playable MP4s.
"""

import os
import sys
import json
import time
import shutil
import argparse
import statistics
from pathlib import Path

# Safe Unicode output for Windows console
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Default CapCut draft paths on Windows
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
DEFAULT_CAPCUT_DRAFT_PATH = os.path.join(
    LOCALAPPDATA, "CapCut", "User Data", "Projects", "com.lveditor.draft"
)

def format_bytes(n):
    if n >= 1048576:
        return f"{n / 1048576:.2f} MB"
    elif n >= 1024:
        return f"{n / 1024:.2f} KB"
    return f"{n} B"

def detect_xor_key(header_bytes):
    """
    Checks if first 16 bytes decode to an MP4 ftyp box under a single-byte XOR key.
    """
    if len(header_bytes) < 16:
        return None
    # If already ftyp, it's clean
    if header_bytes[4:8] == b"ftyp":
        return {"plain": True, "key": 0}
    
    k = header_bytes[4] ^ 0x66  # ASCII 'f' is 0x66
    if (header_bytes[5] ^ k) == 0x74 and (header_bytes[6] ^ k) == 0x79 and (header_bytes[7] ^ k) == 0x70:
        return {"plain": False, "key": k}
    return None

def estimate_pattern(file_path, key):
    """
    Scans the file tail for runs of key-filled bytes vs zero-filled bytes.
    """
    file_size = os.path.getsize(file_path)
    w = min(file_size, 262144)
    start = (file_size - w) & ~3
    
    with open(file_path, "rb") as f:
        f.seek(start)
        tail = f.read(w)
        
    state = ""
    run_start = 0
    starts, lens = [], []
    
    for p in range(0, len(tail) - 4, 4):
        word = tail[p:p+4]
        t = "X" if (word[0] == key and word[1] == key) else ("P" if (word[0] == 0 and word[1] == 0) else "")
        if not t or t == state:
            continue
        if t == "X":
            run_start = p
        elif state == "X":
            if p - run_start >= 64:
                starts.append(run_start)
                lens.append(p - run_start)
        state = t
        
    if len(starts) < 3:
        # Fallback to header-only repair
        return {"P": file_size, "L": 64, "runs": len(starts)}
        
    diffs = [starts[i] - starts[i-1] for i in range(1, len(starts))]
    return {
        "P": int(statistics.median(diffs)),
        "L": int(statistics.median(lens)),
        "runs": len(starts)
    }

def fit_pattern(file_path, key, P_est):
    """
    Histogram-based fine fit of repetition period P and length L.
    """
    file_size = os.path.getsize(file_path)
    w = min(file_size, 262144)
    start = (file_size - w) & ~3
    
    with open(file_path, "rb") as f:
        f.seek(start)
        tail = f.read(w)
        
    xs, zs = [], []
    for p in range(0, len(tail) - 4, 4):
        if tail[p] == key and tail[p+1] == key:
            xs.append(p)
        elif tail[p] == 0 and tail[p+1] == 0:
            zs.append(p)
            
    if len(xs) < 8 or len(zs) < 8:
        return None
        
    best = None
    min_p = int(P_est * 0.85)
    max_p = int(P_est * 1.15)
    
    for P in range(max(4, min_p), max_p + 1):
        bins = (P >> 2) + 2
        hx = [0] * bins
        hz = [0] * bins
        for pos in xs:
            hx[(pos % P) >> 2] += 1
        for pos in zs:
            hz[(pos % P) >> 2] += 1
            
        x_below, z_below = 0, 0
        for j in range(1, bins):
            x_below += hx[j - 1]
            z_below += hz[j - 1]
            v = (len(xs) - x_below) + z_below
            if best is None or v < best["v"]:
                best = {"v": v, "P": P, "L": j * 4}
                
    return best

def descramble_file(input_path, output_path=None, key=None, period=None, length=None, offset=0, in_place=False, progress_callback=None):
    """
    Descrambles an XOR-scrambled video file.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"File not found: {input_path}")
        
    file_size = os.path.getsize(input_path)
    
    # Read header to auto-detect key if not provided
    with open(input_path, "rb") as f:
        hdr = f.read(16)
        
    detect_res = detect_xor_key(hdr)
    if not detect_res:
        if key is None:
            raise ValueError(f"Could not auto-detect XOR key for {input_path}. Specify --key manually.")
    elif detect_res.get("plain"):
        if key is None:
            return {"status": "already_clean", "path": input_path}
    else:
        if key is None:
            key = detect_res["key"]
            
    # Auto-detect pattern if period/length not provided
    if period is None or length is None:
        est = estimate_pattern(input_path, key)
        fitted = fit_pattern(input_path, key, est["P"]) if est["runs"] >= 3 else None
        period = fitted["P"] if fitted else est["P"]
        length = fitted["L"] if fitted else est["L"]
        
    if output_path is None:
        if in_place:
            backup_path = input_path + ".bak"
            if not os.path.exists(backup_path):
                shutil.copy2(input_path, backup_path)
            output_path = input_path
        else:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_CapRecut.mp4"
            
    temp_output = output_path + ".tmp"
    
    # Perform chunked XOR descramble
    chunk_size = 1048576 * 8  # 8 MB buffer
    processed_bytes = 0
    block_index = 0
    
    with open(input_path, "rb") as src, open(temp_output, "wb") as dst:
        file_pos = 0
        while True:
            chunk = src.read(chunk_size)
            if not chunk:
                break
                
            chunk_arr = bytearray(chunk)
            chunk_len = len(chunk_arr)
            chunk_start = file_pos
            chunk_end = file_pos + chunk_len
            
            # Find first block start in or before this chunk
            first_block = ((max(0, chunk_start - offset)) // period) * period + offset
            
            s = first_block
            while s < chunk_end:
                e = s + length
                # Intersect [s, e] with [chunk_start, chunk_end]
                range_start = max(s, chunk_start)
                range_end = min(e, chunk_end)
                
                if range_start < range_end:
                    local_start = range_start - chunk_start
                    local_end = range_end - chunk_start
                    for i in range(local_start, local_end):
                        chunk_arr[i] ^= key
                        
                s += period
                block_index += 1
                
            dst.write(chunk_arr)
            file_pos += chunk_len
            processed_bytes += chunk_len
            
            if progress_callback:
                progress_callback(processed_bytes, file_size)
                
    if os.path.exists(output_path) and output_path == input_path:
        os.remove(input_path)
    os.replace(temp_output, output_path)
    
    return {
        "status": "repaired",
        "input": input_path,
        "output": output_path,
        "key": f"0x{key:02X}",
        "period": period,
        "length": length,
        "size": file_size
    }

def find_capcut_drafts(capcut_dir=None):
    """
    Finds all CapCut draft projects on the system.
    """
    dir_path = capcut_dir or DEFAULT_CAPCUT_DRAFT_PATH
    if not os.path.exists(dir_path):
        return []
        
    drafts = []
    for item in os.listdir(dir_path):
        sub_dir = os.path.join(dir_path, item)
        if os.path.isdir(sub_dir):
            content_file = os.path.join(sub_dir, "draft_content.json")
            meta_file = os.path.join(sub_dir, "draft_meta_info.json")
            
            draft_name = item
            if os.path.exists(meta_file):
                try:
                    with open(meta_file, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                        draft_name = meta.get("draft_name", item)
                except Exception:
                    pass
                    
            drafts.append({
                "id": item,
                "name": draft_name,
                "path": sub_dir,
                "has_content": os.path.exists(content_file),
                "modified": os.path.getmtime(sub_dir)
            })
            
    drafts.sort(key=lambda d: d["modified"], reverse=True)
    return drafts

def scan_draft_for_scrambled_media(draft_path):
    """
    Scans a CapCut draft folder for video files and checks for XOR scrambling.
    """
    scrambled_files = []
    clean_files = []
    
    for root, _, files in os.walk(draft_path):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in [".mp4", ".mov", ".m4v"]:
                full_path = os.path.join(root, f)
                try:
                    with open(full_path, "rb") as vf:
                        hdr = vf.read(16)
                    det = detect_xor_key(hdr)
                    if det and not det.get("plain"):
                        scrambled_files.append({
                            "path": full_path,
                            "filename": f,
                            "size": os.path.getsize(full_path),
                            "key": f"0x{det['key']:02X}",
                            "raw_key": det['key']
                        })
                    else:
                        clean_files.append(full_path)
                except Exception:
                    continue
                    
    return {"scrambled": scrambled_files, "clean_count": len(clean_files)}

# ---------- CLI Commands ----------
def cmd_scan_capcut(args):
    print("\n🔍 Scanning CapCut Drafts on Windows...")
    drafts = find_capcut_drafts(args.capcut_dir)
    if not drafts:
        print(f"⚠️  No CapCut drafts found at: {args.capcut_dir or DEFAULT_CAPCUT_DRAFT_PATH}")
        return
        
    print(f"Found {len(drafts)} CapCut draft projects.\n" + "-" * 70)
    total_scrambled = 0
    
    for d in drafts:
        res = scan_draft_for_scrambled_media(d["path"])
        scrambled = res["scrambled"]
        mod_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(d["modified"]))
        
        status_pill = f"🚨 {len(scrambled)} SCRAMBLED VIDEO(S)" if scrambled else "✅ Clean"
        print(f"📁 Draft [{d['id']}] \"{d['name']}\" ({mod_time}) — {status_pill}")
        
        for sc in scrambled:
            print(f"   ↳ {sc['filename']} ({format_bytes(sc['size'])}) — XOR Key: {sc['key']}")
            total_scrambled += 1
            
    print("-" * 70)
    if total_scrambled > 0:
        print(f"⚠️  Found {total_scrambled} scrambled media files in your CapCut drafts.")
        print("💡 Run: python caprecut_capcut.py repair-draft <id> or --repair-all")
    else:
        print("🎉 All video assets in CapCut drafts are clean and uncorrupted!")

def cmd_repair_draft(args):
    draft_id = args.draft_id
    capcut_dir = args.capcut_dir or DEFAULT_CAPCUT_DRAFT_PATH
    target_path = os.path.join(capcut_dir, draft_id) if not os.path.isabs(draft_id) else draft_id
    
    if not os.path.exists(target_path):
        print(f"❌ CapCut draft folder not found: {target_path}")
        return
        
    print(f"Scanning draft: {target_path}")
    res = scan_draft_for_scrambled_media(target_path)
    scrambled = res["scrambled"]
    
    if not scrambled:
        print("✅ No scrambled video files detected in this draft!")
        return
        
    print(f"Found {len(scrambled)} scrambled file(s). Repairing now...\n")
    for item in scrambled:
        path = item["path"]
        print(f"🛠️  Repairing {item['filename']} (Key: {item['key']}, Size: {format_bytes(item['size'])})…")
        
        def show_progress(proc, total):
            pct = int(proc / total * 100)
            sys.stdout.write(f"\r   Progress: [{'=' * (pct // 4)}{' ' * (25 - pct // 4)}] {pct}%")
            sys.stdout.flush()
            
        result = descramble_file(path, in_place=args.in_place, progress_callback=show_progress)
        print(f"\n   ✅ Done! Repaired output: {result['output']}\n")

def cmd_repair_file(args):
    print(f"🛠️  Descrambling single file: {args.file}")
    key_int = int(args.key, 16) if args.key else None
    
    def show_progress(proc, total):
        pct = int(proc / total * 100)
        sys.stdout.write(f"\rProgress: [{'=' * (pct // 4)}{' ' * (25 - pct // 4)}] {pct}%")
        sys.stdout.flush()
        
    res = descramble_file(
        args.file,
        output_path=args.output,
        key=key_int,
        period=args.period,
        length=args.length,
        offset=args.offset or 0,
        in_place=args.in_place,
        progress_callback=show_progress
    )
    print(f"\n🎉 Repair Complete! Saved to: {res['output']}")
    print(f"   Key: {res['key']} | Period: {res['period']} B | Length: {res['length']} B")

def cmd_watch_capcut(args):
    capcut_dir = args.capcut_dir or DEFAULT_CAPCUT_DRAFT_PATH
    print(f"👀 Watching CapCut drafts directory for new scrambled clips:")
    print(f"   {capcut_dir}")
    print("   (Press Ctrl+C to stop watcher)\n")
    
    seen_files = set()
    while True:
        try:
            for root, _, files in os.walk(capcut_dir):
                for f in files:
                    if f.endswith((".mp4", ".mov", ".m4v")) and not f.endswith("_CapRecut.mp4") and not f.endswith(".bak"):
                        full_p = os.path.join(root, f)
                        if full_p not in seen_files:
                            seen_files.add(full_p)
                            try:
                                with open(full_p, "rb") as chk:
                                    hdr = chk.read(16)
                                det = detect_xor_key(hdr)
                                if det and not det.get("plain"):
                                    print(f"🚨 [New Scrambled Video Detected] {f} in {os.path.basename(root)}")
                                    print(f"   Auto-repairing with key 0x{det['key']:02X}...")
                                    res = descramble_file(full_p, in_place=args.in_place)
                                    print(f"   ✅ Auto-repaired: {res['output']}\n")
                            except Exception:
                                pass
            time.sleep(2.5)
        except KeyboardInterrupt:
            print("\nWatcher stopped.")
            break

def main():
    parser = argparse.ArgumentParser(description="CapRecut — CapCut Companion Plugin & MP4 Descrambler")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")
    
    # scan
    p_scan = subparsers.add_parser("scan-capcut", help="Scan local CapCut drafts for scrambled videos")
    p_scan.add_argument("--capcut-dir", help="Custom CapCut drafts directory")
    
    # repair-draft
    p_draft = subparsers.add_parser("repair-draft", help="Repair scrambled videos in a specific CapCut draft")
    p_draft.add_argument("draft_id", help="Draft ID or folder path (e.g. 1030)")
    p_draft.add_argument("--in-place", action="store_true", help="Repair in-place with .bak backup")
    p_draft.add_argument("--capcut-dir", help="Custom CapCut drafts directory")
    
    # repair-file
    p_file = subparsers.add_parser("repair-file", help="Repair any standalone video file")
    p_file.add_argument("file", help="Input video file path")
    p_file.add_argument("-o", "--output", help="Output file path")
    p_file.add_argument("-k", "--key", help="XOR key in hex (e.g. BE or 0xBE)")
    p_file.add_argument("-p", "--period", type=int, help="Repeat period in bytes")
    p_file.add_argument("-l", "--length", type=int, help="Scrambled block length in bytes")
    p_file.add_argument("--offset", type=int, default=0, help="Start offset in bytes")
    p_file.add_argument("--in-place", action="store_true", help="Replace file with .bak backup")
    
    # watch
    p_watch = subparsers.add_parser("watch-capcut", help="Continuously watch CapCut drafts folder and auto-repair")
    p_watch.add_argument("--capcut-dir", help="Custom CapCut drafts directory")
    p_watch.add_argument("--in-place", action="store_true", help="Auto-repair in-place")
    
    if len(sys.argv) == 1:
        # If no arguments provided, show interactive prompt
        print("=" * 65)
        print("         CapRecut — CapCut Companion Plugin & Tool")
        print("=" * 65)
        print("1. Scan CapCut drafts for scrambled files")
        print("2. Repair media in a CapCut draft (e.g. draft 1030)")
        print("3. Watch CapCut drafts in background (auto-fix new files)")
        print("4. Repair a specific video file (drag & drop)")
        print("5. Open CapRecut Browser UI")
        print("=" * 65)
        choice = input("Select an option (1-5): ").strip()
        
        if choice == "1":
            cmd_scan_capcut(argparse.Namespace(capcut_dir=None))
        elif choice == "2":
            draft_id = input("Enter CapCut Draft ID (e.g. 1030): ").strip() or "1030"
            cmd_repair_draft(argparse.Namespace(draft_id=draft_id, in_place=False, capcut_dir=None))
        elif choice == "3":
            cmd_watch_capcut(argparse.Namespace(capcut_dir=None, in_place=False))
        elif choice == "4":
            fpath = input("Enter video file path or drag & drop here: ").strip().strip('"')
            cmd_repair_file(argparse.Namespace(file=fpath, output=None, key=None, period=None, length=None, offset=0, in_place=False))
        elif choice == "5":
            import webbrowser
            html_path = os.path.join(os.path.dirname(__file__), "CapRecut.html")
            if not os.path.exists(html_path):
                html_path = r"c:\Users\syamm\Downloads\CapRecut.html"
            webbrowser.open(f"file:///{os.path.abspath(html_path)}")
        return
        
    args = parser.parse_args()
    if args.command == "scan-capcut":
        cmd_scan_capcut(args)
    elif args.command == "repair-draft":
        cmd_repair_draft(args)
    elif args.command == "repair-file":
        cmd_repair_file(args)
    elif args.command == "watch-capcut":
        cmd_watch_capcut(args)

if __name__ == "__main__":
    main()
