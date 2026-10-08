#!/usr/bin/env python3
"""
download_datasets.py - Resilient Kaggle Dataset Downloader Engine

Acquires datasets from Kaggle with:
  1. Multi-tier authentication hierarchy (KAGGLE_API_TOKEN, access_token file, legacy, anonymous).
  2. Resumable downloads via HTTP Range headers and .kaggle-partial markers.
  3. Local NVMe staging for new downloads to avoid Google Drive VFS sync contention, followed
     by archive integrity testing and atomic movement into target directory.
  4. 8MB chunk streaming with live tqdm progress bars (MB/s throughput and ETA).
  5. Exponential backoff retry logic with jitter and dynamic signed URL renewal on network drops.
"""

import argparse
import datetime
import json
import os
import random
import shutil
import sys
import tempfile
import time
import zipfile
from typing import Dict, List, Optional, Tuple

import requests
import urllib3
from tqdm import tqdm

try:
    from kaggle.api.kaggle_api_extended import KaggleApi
    from kagglesdk.datasets.types.dataset_api_service import ApiDownloadDatasetRequest
except ImportError as e:
    sys.exit(f"Error: Missing required kaggle package ({e}). Please install via 'pip install kaggle'.")

DEFAULT_TARGET_DIR = r"I:\My Drive\1509-chakramodelom\dataet"
DEFAULT_STAGING_DIR = os.path.join(tempfile.gettempdir(), "kaggle_staging")
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB
DEFAULT_MAX_RETRIES = 5

DEFAULT_DATASETS = [
    # Batch 1 (Initial Scope - Acquired & Verified)
    "gokulraj324/polypgen20021-video",
    "gokulrocky/endoscene-cvc300-polyp-raw-dataset",
    "gokulrocky/cvc-sample-video",
    # Batch 2 (Scope Expansion - 8 Additional Datasets)
    "gokulrocky/hperkvasir-labeled-videos-part2-002",
    "gokulrocky/hyperkvasir-labeled-videos-part2-001",
    "gokulrocky/hyperkvasir-dataset-first-half-and-and-ld-dataset",
    "gokulrocky/chakramodel-evaluation-datasets",
    "gokulrocky/final-om-evlautation-upload",
    "gokulraj324/ldpolypvideopolyponly",
    "gokulraj324/ldpolypvideowithoutpolyps",
    "gokulrocky/polypdb-polyp-raw",
]

DATASET_ALIASES = {
    # Resolved Kaggle upstream aliases for datasets whose slugs differ between local naming and Kaggle repository
    "gokulrocky/final-om-evlautation-upload": "gokulrocky/finalmuruga-harae",
    "gokulrocky/final-om-evaluation-upload": "gokulrocky/finalmuruga-harae",
}



def resolve_auth(token_arg: Optional[str] = None) -> KaggleApi:
    """
    Resolve Kaggle authentication across 5-tier hierarchy:
      Tier 1: Explicit CLI argument or KAGGLE_API_TOKEN environment variable.
      Tier 2: API token file at ~/.kaggle/access_token.
      Tier 3: Legacy environment variables KAGGLE_USERNAME & KAGGLE_KEY.
      Tier 4: Legacy credentials file at ~/.kaggle/kaggle.json.
      Tier 5: Public anonymous access fallback.
    """
    token = token_arg or os.environ.get("KAGGLE_API_TOKEN")
    access_token_file = os.path.expanduser(os.path.join("~", ".kaggle", "access_token"))
    legacy_json_file = os.path.expanduser(os.path.join("~", ".kaggle", "kaggle.json"))

    auth_source = "None"
    if token:
        os.environ["KAGGLE_API_TOKEN"] = token
        auth_source = "Tier 1: KAGGLE_API_TOKEN (env/argument)"
    elif os.path.exists(access_token_file) and os.path.getsize(access_token_file) > 0:
        auth_source = f"Tier 2: Token file ({access_token_file})"
        try:
            with open(access_token_file, "r", encoding="utf-8") as f:
                tok = f.read().strip()
                if tok:
                    os.environ["KAGGLE_API_TOKEN"] = tok
        except Exception as tok_err:
            print(f"[!] Warning reading {access_token_file}: {tok_err}")
    elif os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        auth_source = "Tier 3: Legacy env vars (KAGGLE_USERNAME/KEY)"
    elif os.path.exists(legacy_json_file) and os.path.getsize(legacy_json_file) > 0:
        auth_source = f"Tier 4: Legacy file ({legacy_json_file})"
    else:
        auth_source = "Tier 5: Public anonymous fallback"

    print(f"[*] Authenticating with Kaggle [{auth_source}]...")
    api = KaggleApi()
    try:
        api.authenticate()
        print(f"[+] Kaggle authentication successful (Method: {getattr(api, 'auth_method', 'active')}).")
        return api
    except Exception as e:
        print(f"[!] Standard authentication raised ({e}). Attempting anonymous fallback...")
        try:
            api._authenticated = True
            print("[+] Configured Kaggle client for anonymous public access.")
            return api
        except Exception as anon_err:
            print(f"[-] Anonymous configuration error: {anon_err}")
            raise


def safe_remove_file(filepath: str, max_attempts: int = 5, delay: float = 0.5) -> bool:
    """Safely delete a file with retry loop for Windows file lock / WinError 32."""
    if not os.path.exists(filepath):
        return True
    for attempt in range(max_attempts):
        try:
            os.remove(filepath)
            return True
        except (PermissionError, OSError) as e:
            time.sleep(delay * (attempt + 1))
    print(f"[!] Warning: Could not remove temporary file {filepath} (file in use).")
    return False


def safe_move_file(src: str, dst: str, max_attempts: int = 5, delay: float = 1.0) -> bool:
    """Atomically move a file with retries to withstand Google Drive VFS background locks."""
    dst_dir = os.path.dirname(dst)
    os.makedirs(dst_dir, exist_ok=True)
    for attempt in range(max_attempts):
        try:
            shutil.move(src, dst)
            return True
        except (PermissionError, OSError) as e:
            print(f"[!] Move attempt {attempt + 1}/{max_attempts} failed ({e}). Retrying in {delay}s...")
            time.sleep(delay * (attempt + 1))
    raise OSError(f"Failed to move {src} to {dst} after {max_attempts} attempts.")


def normalize_validator(v: Optional[str]) -> Optional[str]:
    """Strip surrounding quotes and whitespace for robust ETag comparison."""
    if v is None:
        return None
    return v.strip().strip('"').strip("'")


def read_partial_marker(partial_path: str) -> Optional[Dict]:
    """Read .kaggle-partial sidecar file containing validator and expected size."""
    if not os.path.isfile(partial_path):
        return None
    try:
        with open(partial_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "validator" in data:
                return data
    except Exception as e:
        print(f"[!] Notice: Unable to parse partial marker {partial_path}: {e}")
    return None


def write_partial_marker(partial_path: str, validator: Optional[str], size: Optional[int]) -> None:
    """Persist .kaggle-partial sidecar file."""
    if not validator:
        return
    try:
        with open(partial_path, "w", encoding="utf-8") as f:
            json.dump({"validator": validator, "size": size}, f)
    except Exception as e:
        print(f"[!] Warning: Could not write partial marker {partial_path}: {e}")


def get_fresh_download_response(api: KaggleApi, owner_slug: str, dataset_slug: str) -> requests.Response:
    """Request a fresh download stream from Kaggle to renew Google Cloud Storage signed URLs."""
    spec_key = f"{owner_slug}/{dataset_slug}"
    canonical_spec = DATASET_ALIASES.get(spec_key, spec_key)
    c_owner, c_slug = canonical_spec.split("/")

    with api.build_kaggle_client() as client:
        req = ApiDownloadDatasetRequest()
        req.owner_slug = owner_slug
        req.dataset_slug = dataset_slug
        try:
            response = client.datasets.dataset_api_client.download_dataset(req)
            return response
        except Exception as e:
            if canonical_spec != spec_key:
                print(f"[i] Primary slug '{spec_key}' returned ({e}). Falling back to verified upstream slug '{canonical_spec}'...")
                req.owner_slug = c_owner
                req.dataset_slug = c_slug
                response = client.datasets.dataset_api_client.download_dataset(req)
                return response
            raise


def verify_archive_integrity(archive_path: str) -> Tuple[bool, Optional[str]]:
    """Verify archive zip structure and CRC32 of all inner members."""
    if not os.path.isfile(archive_path) or os.path.getsize(archive_path) == 0:
        return False, "File is missing or empty"
    try:
        with zipfile.ZipFile(archive_path, "r") as z:
            corrupt = z.testzip()
            if corrupt is not None:
                return False, f"Corrupted archive member: {corrupt}"
            return True, None
    except zipfile.BadZipFile as e:
        return False, f"BadZipFile: {e}"
    except Exception as e:
        return False, f"Integrity check failed: {e}"


def stream_with_resilience(
    api: KaggleApi,
    owner_slug: str,
    dataset_slug: str,
    outfile: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> bool:
    """
    Stream download a dataset with HTTP Range resumption, 8MB chunking,
    and exponential backoff retry with dynamic URL renewal.
    """
    partial_marker_path = outfile + ".kaggle-partial"
    out_dir = os.path.dirname(outfile)
    os.makedirs(out_dir, exist_ok=True)

    retry_count = 0
    while retry_count <= max_retries:
        session = requests.Session()
        resp = None
        try:
            # 1. Obtain a fresh signed download URL and headers from Kaggle
            resp = get_fresh_download_response(api, owner_slug, dataset_slug)
            content_length = resp.headers.get("Content-Length")
            remote_size = int(content_length) if content_length else None
            etag = resp.headers.get("ETag")
            last_modified = resp.headers.get("Last-Modified")
            validator = etag or last_modified
            accept_ranges = resp.headers.get("Accept-Ranges") == "bytes"
            download_url = resp.url

            # Close the Kaggle API response wrapper to release connection
            resp.close()

            # 2. Inspect local file state and resume capability
            file_exists = os.path.isfile(outfile)
            local_size = os.path.getsize(outfile) if file_exists else 0
            partial_marker = read_partial_marker(partial_marker_path)

            # Check if file is already complete and uncorrupted
            if remote_size is not None and local_size == remote_size:
                print(f"[i] File {os.path.basename(outfile)} is already fully downloaded ({local_size:,} bytes).")
                valid, err = verify_archive_integrity(outfile)
                if valid:
                    print(f"[+] Verified archive integrity for {os.path.basename(outfile)}.")
                    safe_remove_file(partial_marker_path)
                    return True
                else:
                    print(f"[!] Existing file failed integrity check ({err}). Restarting download from scratch...")
                    local_size = 0

            # 3. Determine if we can resume using HTTP Range
            stored_val = normalize_validator(partial_marker.get("validator")) if partial_marker else None
            remote_val = normalize_validator(validator)
            can_resume = (
                local_size > 0
                and stored_val is not None
                and stored_val == remote_val
                and (remote_size is None or local_size < remote_size)
            )

            req_headers = {}
            open_mode = "wb"
            initial_pos = 0

            if can_resume:
                req_headers["Range"] = f"bytes={local_size}-"
                if validator:
                    req_headers["If-Range"] = validator
                print(
                    f"[*] Resuming {dataset_slug} from byte {local_size:,} "
                    f"({(local_size / remote_size * 100):.2f}% done, "
                    f"{((remote_size - local_size) / (1024*1024)):.2f} MB remaining)..."
                )
                stream_resp = session.get(download_url, headers=req_headers, stream=True, timeout=300)

                if stream_resp.status_code == 206:
                    open_mode = "ab"
                    initial_pos = local_size
                elif stream_resp.status_code == 200:
                    print("[!] Server returned 200 OK (Range ignored or updated upstream). Restarting from byte 0.")
                    open_mode = "wb"
                    initial_pos = 0
                    local_size = 0
                    write_partial_marker(partial_marker_path, validator, remote_size)
                else:
                    stream_resp.raise_for_status()
            else:
                if local_size > 0:
                    print(f"[*] Overwriting stale/mismatched local file ({local_size:,} bytes) with fresh download.")
                else:
                    print(f"[*] Starting fresh download of {dataset_slug} ({remote_size:,} bytes)...")
                write_partial_marker(partial_marker_path, validator, remote_size)
                stream_resp = session.get(download_url, stream=True, timeout=300)
                stream_resp.raise_for_status()
                open_mode = "wb"
                initial_pos = 0
                local_size = 0

            # 4. Stream chunks to disk with progress tracking
            bytes_since_sync = 0
            with tqdm(
                total=remote_size,
                initial=initial_pos,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc=os.path.basename(outfile),
                leave=True,
            ) as pbar:
                with open(outfile, open_mode) as f:
                    for chunk in stream_resp.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        f.write(chunk)
                        f.flush()
                        chunk_len = len(chunk)
                        local_size += chunk_len
                        pbar.update(chunk_len)
                        bytes_since_sync += chunk_len

                        # Flush to underlying disk every 64MB
                        if bytes_since_sync >= 64 * 1024 * 1024:
                            os.fsync(f.fileno())
                            bytes_since_sync = 0

                    os.fsync(f.fileno())

            stream_resp.close()

            # 5. Verify downloaded file size
            final_size = os.path.getsize(outfile)
            if remote_size is not None and final_size != remote_size:
                raise ValueError(
                    f"Size mismatch: downloaded {final_size:,} bytes, expected {remote_size:,} bytes."
                )

            # Success
            return True

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.HTTPError,
            urllib3.exceptions.ProtocolError,
            urllib3.exceptions.ReadTimeoutError,
            OSError,
            ValueError,
        ) as e:
            retry_count += 1
            if resp:
                resp.close()

            if retry_count > max_retries:
                print(f"\n[-] ERROR: Download failed for {dataset_slug} after {max_retries} attempts.")
                print(f"    Details: {type(e).__name__}: {e}")
                return False

            backoff = min(2.0 * (1.8 ** (retry_count - 1)) + random.uniform(0.5, 2.0), 60.0)
            # Check for HTTP 429 Retry-After header
            if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
                if e.response.status_code == 429:
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        backoff = max(float(retry_after), backoff)

            print(f"\n[!] Network issue encountered ({type(e).__name__}: {e}).")
            print(f"    Retry {retry_count}/{max_retries} scheduled in {backoff:.1f} seconds...")
            time.sleep(backoff)


def download_dataset_workflow(
    api: KaggleApi,
    dataset_spec: str,
    target_dir: str,
    staging_dir: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> bool:
    """
    Execute end-to-end download workflow for a single dataset:
    - If partial exists in target_dir, resume in-place.
    - Otherwise, download to staging_dir on NVMe SSD, verify integrity, and atomically move.
    """
    parts = dataset_spec.strip().split("/")
    if len(parts) != 2:
        print(f"[-] Invalid dataset format: '{dataset_spec}'. Expected 'owner/dataset-name'.")
        return False
    owner_slug, dataset_slug = parts[0], parts[1]
    archive_filename = f"{dataset_slug}.zip"

    target_archive = os.path.join(target_dir, archive_filename)
    target_partial = target_archive + ".kaggle-partial"

    staging_archive = os.path.join(staging_dir, archive_filename)
    staging_partial = staging_archive + ".kaggle-partial"

    # Scenario A: Check if existing complete archive is already present in target_dir
    if os.path.isfile(target_archive) and not os.path.isfile(target_partial):
        valid, _ = verify_archive_integrity(target_archive)
        if valid:
            print(f"[+] Dataset '{dataset_slug}' is already complete and verified in target directory.")
            return True

    # Scenario B: Resumable download in target directory (e.g. existing partial file)
    if os.path.isfile(target_archive) and os.path.isfile(target_partial):
        print(f"[*] Detected existing partial file in target directory for '{dataset_slug}'. Resuming in-place...")
        success = stream_with_resilience(
            api=api,
            owner_slug=owner_slug,
            dataset_slug=dataset_slug,
            outfile=target_archive,
            chunk_size=chunk_size,
            max_retries=max_retries,
        )
        if not success:
            return False

        print(f"[*] Validating archive integrity for '{archive_filename}'...")
        valid, err = verify_archive_integrity(target_archive)
        if not valid:
            print(f"[-] CRC32 archive integrity failed for '{target_archive}': {err}")
            return False

        safe_remove_file(target_partial)
        print(f"[+] Successfully completed and verified '{archive_filename}' in target directory.")
        return True

    # Scenario C: New download staged on fast local NVMe SSD (staging_dir)
    print(f"[*] Downloading '{dataset_slug}' via staging directory: {staging_dir}")
    os.makedirs(staging_dir, exist_ok=True)
    success = stream_with_resilience(
        api=api,
        owner_slug=owner_slug,
        dataset_slug=dataset_slug,
        outfile=staging_archive,
        chunk_size=chunk_size,
        max_retries=max_retries,
    )
    if not success:
        return False

    print(f"[*] Running pre-transfer archive integrity test on staging file...")
    valid, err = verify_archive_integrity(staging_archive)
    if not valid:
        print(f"[-] Staged archive integrity check failed: {err}")
        return False

    safe_remove_file(staging_partial)

    print(f"[*] Atomically moving '{archive_filename}' from staging to target directory...")
    safe_move_file(staging_archive, target_archive)
    print(f"[+] Transferred '{archive_filename}' to {target_dir} successfully.")

    # Mirror alias archive if applicable
    canonical_spec = DATASET_ALIASES.get(dataset_spec)
    if canonical_spec:
        canonical_slug = canonical_spec.split("/")[1]
        canonical_archive = os.path.join(target_dir, f"{canonical_slug}.zip")
        if not os.path.exists(canonical_archive):
            try:
                os.link(target_archive, canonical_archive)
                print(f"[+] Created hardlink {canonical_slug}.zip -> {archive_filename}")
            except Exception:
                try:
                    shutil.copy2(target_archive, canonical_archive)
                    print(f"[+] Created mirror copy {canonical_slug}.zip -> {archive_filename}")
                except Exception as mirror_err:
                    print(f"[!] Warning creating mirror {canonical_slug}.zip: {mirror_err}")

    return True


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Resilient Kaggle Dataset Downloader Engine with Range Resumption and Staging."
    )
    parser.add_argument(
        "--target-dir",
        default=DEFAULT_TARGET_DIR,
        help=f"Target directory for acquired datasets (default: {DEFAULT_TARGET_DIR})",
    )
    parser.add_argument(
        "--staging-dir",
        default=DEFAULT_STAGING_DIR,
        help=f"Fast local staging directory for downloads (default: {DEFAULT_STAGING_DIR})",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=DEFAULT_DATASETS,
        help="One or more Kaggle dataset identifiers (owner/dataset-name).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Streaming chunk buffer size in bytes (default: {DEFAULT_CHUNK_SIZE} = 8MB)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Maximum retry attempts on transient network drops (default: {DEFAULT_MAX_RETRIES})",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Optional Kaggle API Token (overrides or falls back to KAGGLE_API_TOKEN)",
    )

    parsed_args = parser.parse_args(args)

    if parsed_args.chunk_size <= 0:
        parser.error(f"--chunk-size must be a positive integer (> 0), got {parsed_args.chunk_size}")
    if parsed_args.max_retries < 0:
        parser.error(f"--max-retries must be non-negative (>= 0), got {parsed_args.max_retries}")

    return parsed_args


def main():
    args = parse_args()

    print("=" * 70)
    print("           KAGGLE RESILIENT DATASET DOWNLOADER ENGINE")
    print("=" * 70)
    print(f"Target Directory : {args.target_dir}")
    print(f"Staging Directory: {args.staging_dir}")
    print(f"Chunk Size       : {args.chunk_size:,} bytes ({(args.chunk_size / (1024*1024)):.1f} MB)")
    print(f"Max Retries      : {args.max_retries}")
    print(f"Datasets ({len(args.datasets)}):")
    for ds in args.datasets:
        print(f"  - {ds}")
    print("=" * 70)

    # 1. Authenticate
    api = resolve_auth(args.token)

    # 2. Process Datasets
    success_count = 0
    start_time = time.time()

    for idx, ds in enumerate(args.datasets, start=1):
        print(f"\n--- [{idx}/{len(args.datasets)}] Processing: {ds} ---")
        ok = download_dataset_workflow(
            api=api,
            dataset_spec=ds,
            target_dir=args.target_dir,
            staging_dir=args.staging_dir,
            chunk_size=args.chunk_size,
            max_retries=args.max_retries,
        )
        if ok:
            success_count += 1
        else:
            print(f"[-] Failed to acquire dataset: {ds}")

    total_time = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"DOWNLOAD SUMMARY: {success_count}/{len(args.datasets)} datasets successfully acquired.")
    print(f"Total Elapsed Time: {total_time:.1f} seconds ({total_time / 60:.2f} minutes).")
    print("=" * 70)

    if success_count == len(args.datasets):
        print("[+] All target datasets acquired successfully.")
        sys.exit(0)
    else:
        print("[-] One or more datasets failed to download.")
        sys.exit(1)


if __name__ == "__main__":
    main()
