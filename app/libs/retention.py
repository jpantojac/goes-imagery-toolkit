#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GOES Imagery Toolkit - Storage Retention & Disk Pruning Engine
===============================================================

Manages automated storage life-cycles for raw telemetry and intermediate satellite rasters (.nc, .raw)
as well as historical cartographic output products (.png, .pgw, .tif).

Features:
- Configurable retention in hours for raw inputs (default: 24h, supports any hourly duration, e.g. 3h)
- Configurable retention in days for output products (default: 30 days, or 0 for permanent retention)
- Emergency disk capacity threshold safeguards (e.g. 85% disk usage or <5GB free)
- Automatic pruning of empty Julian day directories
- Non-destructive execution: permanently protects latest/ preview products
- Dry-run simulation mode for administrative planning

Author: Julian Pantoja Clavijo <julianpc.dev@gmail.com>
License: MIT
"""
import os
import shutil
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple


def parse_file_datetime(filepath: str) -> datetime:
    """
    Extracts the observation UTC datetime from satellite file naming conventions,
    falling back to filesystem modification time (mtime) if naming is non-standard.

    Args:
        filepath (str): Full path or filename of target file.

    Returns:
        datetime: UTC datetime representing observation or modification time.
    """
    filename = os.path.basename(filepath)

    # 1. NOAA ABI format: OR_ABI-L1b-RadF-M6C..._sYYYYJJJHHMMSS..._c...nc
    s_idx = filename.find('_s')
    if s_idx != -1 and len(filename) >= s_idx + 13:
        try:
            s_part = filename[s_idx + 2 : s_idx + 15]
            year = int(s_part[0:4])
            julian_day = int(s_part[4:7])
            hour = int(s_part[7:9])
            minute = int(s_part[9:11])
            return datetime(year, 1, 1, hour, minute, tzinfo=timezone.utc) + timedelta(days=julian_day - 1)
        except Exception:
            pass

    # 2. Output products format: YYYYMMDDHHMM.<ext> (e.g. 202611181200.png)
    base_name = os.path.splitext(filename)[0]
    if len(base_name) == 12 and base_name.isdigit():
        try:
            year = int(base_name[0:4])
            month = int(base_name[4:6])
            day = int(base_name[6:8])
            hour = int(base_name[8:10])
            minute = int(base_name[10:12])
            return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        except Exception:
            pass

    # 3. Fallback: filesystem modification timestamp
    try:
        mtime = os.path.getmtime(filepath)
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def get_disk_status(path: str = ".") -> Tuple[float, float, float]:
    """
    Retrieves storage capacity metrics for the filesystem hosting the given path.

    Args:
        path (str, optional): Target directory path. Defaults to ".".

    Returns:
        Tuple[float, float, float]: (used_percent, free_gb, total_gb)
    """
    try:
        total, used, free = shutil.disk_usage(os.path.abspath(path))
        gb = 1024 ** 3
        used_pct = (used / total) * 100.0 if total > 0 else 0.0
        free_gb = free / gb
        total_gb = total / gb
        return used_pct, free_gb, total_gb
    except Exception:
        return 0.0, 999.0, 999.0


def purge_input_files(
    input_dir: str,
    retention_hours: float,
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Purges raw input files (.nc, .raw, .tmp) older than retention_hours.

    Args:
        input_dir (str): Root input directory path containing Julian day subfolders.
        retention_hours (float): Maximum age threshold in hours.
        dry_run (bool, optional): If True, computes metrics without deleting files. Defaults to False.

    Returns:
        Tuple[int, int]: (files_deleted, bytes_freed)
    """
    if retention_hours <= 0 or not os.path.isdir(input_dir):
        return 0, 0

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=retention_hours)

    files_deleted = 0
    bytes_freed = 0

    for root, _, files in os.walk(input_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                f_dt = parse_file_datetime(fpath)
                if f_dt < cutoff:
                    fsize = os.path.getsize(fpath)
                    if not dry_run:
                        os.remove(fpath)
                    files_deleted += 1
                    bytes_freed += fsize
            except Exception as e:
                logging.warning(f"Could not purge raw file {fpath}: {e}")

    return files_deleted, bytes_freed


def purge_output_files(
    output_dir: str,
    retention_days: float,
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Purges historical products in output_dir (.png, .pgw, .tif) older than retention_days.

    Args:
        output_dir (str): Root output directory path containing Julian day subfolders.
        retention_days (float): Maximum age threshold in days.
        dry_run (bool, optional): If True, computes metrics without deleting files. Defaults to False.

    Returns:
        Tuple[int, int]: (files_deleted, bytes_freed)
    """
    if retention_days <= 0 or not os.path.isdir(output_dir):
        return 0, 0

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)

    files_deleted = 0
    bytes_freed = 0

    for root, _, files in os.walk(output_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                f_dt = parse_file_datetime(fpath)
                if f_dt < cutoff:
                    fsize = os.path.getsize(fpath)
                    if not dry_run:
                        os.remove(fpath)
                    files_deleted += 1
                    bytes_freed += fsize
            except Exception as e:
                logging.warning(f"Could not purge output file {fpath}: {e}")

    return files_deleted, bytes_freed


def emergency_disk_cleanup(
    base_path: str,
    input_dir: str,
    threshold_percent: float = 85.0,
    min_free_gb: float = 5.0,
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Emergency disk protection: if disk usage exceeds threshold_percent or free disk
    falls below min_free_gb, aggressively purges oldest raw input files until safe.

    Args:
        base_path (str): Base filesystem path to monitor disk usage.
        input_dir (str): Root input directory containing raw files.
        threshold_percent (float, optional): Maximum allowable disk usage percent. Defaults to 85.0.
        min_free_gb (float, optional): Minimum required free disk space in GB. Defaults to 5.0.
        dry_run (bool, optional): If True, simulates deletion. Defaults to False.

    Returns:
        Tuple[int, int]: (files_deleted, bytes_freed)
    """
    if not os.path.isdir(input_dir):
        return 0, 0

    used_pct, free_gb, _ = get_disk_status(base_path)
    if used_pct <= threshold_percent and free_gb >= min_free_gb:
        return 0, 0

    logging.warning(
        f"[Emergency Disk Safeguard] Disk usage at {used_pct:.1f}% ({free_gb:.1f} GB free). "
        f"Limit is {threshold_percent:.1f}% / {min_free_gb:.1f} GB min. Purging oldest raw files..."
    )

    raw_candidates = []
    for root, _, files in os.walk(input_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                dt = parse_file_datetime(fpath)
                size = os.path.getsize(fpath)
                raw_candidates.append((dt, size, fpath))
            except Exception:
                pass

    raw_candidates.sort(key=lambda x: x[0])  # Oldest first

    files_deleted = 0
    bytes_freed = 0

    for dt, size, fpath in raw_candidates:
        try:
            if not dry_run:
                os.remove(fpath)
            files_deleted += 1
            bytes_freed += size
        except Exception as e:
            logging.warning(f"Emergency cleanup could not delete {fpath}: {e}")

        used_pct, free_gb, _ = get_disk_status(base_path)
        if used_pct <= threshold_percent and free_gb >= min_free_gb:
            break

    return files_deleted, bytes_freed


def prune_empty_directories(base_dir: str, dry_run: bool = False) -> int:
    """
    Removes empty subdirectories in bottom-up traversal.

    Args:
        base_dir (str): Root directory to clean.
        dry_run (bool, optional): If True, simulates pruning. Defaults to False.

    Returns:
        int: Total number of empty directories removed.
    """
    if not os.path.isdir(base_dir):
        return 0

    pruned = 0
    for root, dirs, _ in os.walk(base_dir, topdown=False):
        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                if not os.listdir(dir_path):
                    if not dry_run:
                        os.rmdir(dir_path)
                    pruned += 1
            except Exception:
                pass
    return pruned


def run_retention_cycle(
    base_path: str,
    config: Optional[Dict[str, Any]] = None,
    raw_hours_override: Optional[float] = None,
    output_days_override: Optional[float] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Executes a comprehensive data retention and storage cleanup cycle.

    Workflow:
        1. Purges raw input files (.nc, .raw) older than raw_retention_hours.
        2. Purges historical output products (.png, .pgw, .tif) older than output_retention_days.
        3. Checks disk threshold; triggers emergency purge of oldest raw files if disk usage is critical.
        4. Prunes empty Julian day subdirectories.

    Args:
        base_path (str): Base project directory path.
        config (Optional[Dict[str, Any]], optional): Parsed config dictionary. Defaults to None.
        raw_hours_override (Optional[float], optional): CLI override for raw hours. Defaults to None.
        output_days_override (Optional[float], optional): CLI override for output days. Defaults to None.
        dry_run (bool, optional): If True, simulates operations without deleting files. Defaults to False.

    Returns:
        Dict[str, Any]: Execution statistics dictionary.
    """
    cfg = config or {}
    ret_cfg = cfg.get('retention', {})

    enabled = ret_cfg.get('enabled', True)
    if not enabled and raw_hours_override is None and output_days_override is None:
        return {}

    raw_hours = raw_hours_override if raw_hours_override is not None else float(ret_cfg.get('raw_retention_hours', 24.0))
    output_days = output_days_override if output_days_override is not None else float(ret_cfg.get('output_retention_days', 30.0))
    disk_threshold = float(ret_cfg.get('disk_threshold_percent', 85.0))
    min_free_gb = float(ret_cfg.get('min_free_disk_gb', 5.0))
    clean_folders = bool(ret_cfg.get('clean_empty_folders', True))

    input_path = os.path.join(base_path, cfg.get('paths', {}).get('input', 'input'))
    output_path = os.path.join(base_path, cfg.get('paths', {}).get('output', 'output'))

    # 1. Purge raw input files older than raw_hours
    raw_del, raw_bytes = purge_input_files(input_path, raw_hours, dry_run=dry_run)

    # 2. Purge output products older than output_days
    out_del, out_bytes = purge_output_files(output_path, output_days, dry_run=dry_run)

    # 3. Emergency disk cleanup if threshold exceeded
    emg_del, emg_bytes = emergency_disk_cleanup(
        base_path, input_path, threshold_percent=disk_threshold, min_free_gb=min_free_gb, dry_run=dry_run
    )

    # 4. Prune empty folders
    pruned_dirs = 0
    if clean_folders:
        pruned_dirs += prune_empty_directories(input_path, dry_run=dry_run)
        pruned_dirs += prune_empty_directories(output_path, dry_run=dry_run)

    total_del = raw_del + out_del + emg_del
    total_freed_mb = (raw_bytes + out_bytes + emg_bytes) / (1024 ** 2)
    used_pct, free_gb, total_gb = get_disk_status(base_path)

    stats = {
        "raw_deleted": raw_del,
        "raw_freed_mb": raw_bytes / (1024 ** 2),
        "output_deleted": out_del,
        "output_freed_mb": out_bytes / (1024 ** 2),
        "emergency_deleted": emg_del,
        "emergency_freed_mb": emg_bytes / (1024 ** 2),
        "total_deleted": total_del,
        "total_freed_mb": total_freed_mb,
        "dirs_pruned": pruned_dirs,
        "disk_free_gb": free_gb,
        "disk_used_percent": used_pct,
        "dry_run": dry_run
    }

    if total_del > 0 or pruned_dirs > 0:
        prefix = "[Retention Dry-Run]" if dry_run else "[Retention Cleanup]"
        logging.info(
            f"{prefix} Removed {total_del} file(s) ({total_freed_mb:.1f} MB freed: "
            f"raw={raw_del}, out={out_del}, emergency={emg_del}) and pruned {pruned_dirs} empty dir(s). "
            f"Disk free: {free_gb:.1f} GB ({used_pct:.1f}% used)."
        )
    else:
        logging.debug(f"[Retention] No files expired. Disk free: {free_gb:.1f} GB ({used_pct:.1f}% used).")

    return stats
