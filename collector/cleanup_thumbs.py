#!/usr/bin/env python3
"""
Thumbnail deduplication and snapshot fixer.

Usage:
  python collector/cleanup_thumbs.py [--snapshots snapshots_dir] [--threshold 8] [--apply]

Default snapshots_dir is "snapshots" at the repo root.
Without --apply, runs in dry-run mode and prints what would change.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def hamming_distance_hex(a: str, b: str) -> int:
    n = min(len(a), len(b))
    if n == 0:
        return 64  # max for 64-bit hash
    try:
        va = int(a[:n], 16)
        vb = int(b[:n], 16)
    except ValueError:
        return 64
    x = va ^ vb
    return int(bin(x).count("1"))


def group_similar_hashes(files: List[Path], threshold_bits: int) -> List[List[Path]]:
    groups: List[List[Path]] = []
    reps: List[str] = []
    for f in files:
        stem = f.stem.lower()
        placed = False
        for i, rep in enumerate(reps):
            if hamming_distance_hex(stem, rep) <= threshold_bits:
                groups[i].append(f)
                placed = True
                break
        if not placed:
            groups.append([f])
            reps.append(stem)
    return groups


def choose_canonical(file_group: List[Path]) -> Path:
    # Choose oldest file by mtime as canonical
    return sorted(file_group, key=lambda p: p.stat().st_mtime)[0]


def update_snapshots(snapshots_dir: Path, mapping_old_to_new: Dict[str, str], apply: bool) -> int:
    changed = 0
    # Only top-level JSON snapshot files: YYYY-MM-DD_HH-MM.json
    for snap in snapshots_dir.glob("*.json"):
        try:
            data = json.loads(snap.read_text(encoding="utf-8"))
        except Exception:
            continue
        cats = data.get("categories", {})
        modified = False
        for cat, items in list(cats.items()):
            if not isinstance(items, list):
                continue
            for item in items:
                rel = item.get("thumbPath")
                if not rel:
                    continue
                # Normalize to POSIX-like within snapshots
                rel_norm = rel.replace("\\", "/")
                if rel_norm.startswith("thumbs/"):
                    fname = rel_norm.split("/", 1)[1]
                    if fname in mapping_old_to_new and mapping_old_to_new[fname] != fname:
                        item["thumbPath"] = f"thumbs/{mapping_old_to_new[fname]}"
                        modified = True
        if modified:
            changed += 1
            if apply:
                snap.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", default="snapshots", help="Snapshots directory (default: snapshots)")
    parser.add_argument("--threshold", type=int, default=8, help="Hamming distance threshold (bits)")
    parser.add_argument("--apply", action="store_true", help="Apply changes (rename in snapshots and delete duplicates)")
    args = parser.parse_args()

    snapshots_dir = Path(args.snapshots).resolve()
    thumbs_dir = snapshots_dir / "thumbs"
    if not thumbs_dir.exists():
        print(f"No thumbnails directory found: {thumbs_dir}")
        return 0

    files = sorted([p for p in thumbs_dir.glob("*.png") if p.is_file()])
    if not files:
        print("No thumbnail files to process.")
        return 0

    groups = group_similar_hashes(files, args.threshold)
    # Build mapping old filename -> canonical filename
    mapping: Dict[str, str] = {}
    to_delete: List[Path] = []

    for group in groups:
        if len(group) == 1:
            fname = group[0].name
            mapping[fname] = fname
            continue
        canonical = choose_canonical(group)
        canon_name = canonical.name
        for f in group:
            mapping[f.name] = canon_name
        # all non-canonical are candidates for deletion
        to_delete.extend([f for f in group if f != canonical])

    # Report groups
    merged = sum(1 for k, v in mapping.items() if k != v)
    print(f"Found {len(groups)} groups across {len(files)} files. {merged} files map to existing canonical files.")

    # Update snapshots
    changed = update_snapshots(snapshots_dir, mapping, apply=args.apply)
    print(f"Snapshots updated: {changed}{' (applied)' if args.apply else ' (dry-run)'}")

    # Delete duplicates
    if args.apply and to_delete:
        for f in to_delete:
            try:
                f.unlink()
            except Exception:
                pass
        print(f"Deleted {len(to_delete)} duplicate thumbnail files.")
    else:
        print(f"Duplicate candidates: {len(to_delete)} (use --apply to delete)")

    return 0


if __name__ == "__main__":
    sys.exit(main())


