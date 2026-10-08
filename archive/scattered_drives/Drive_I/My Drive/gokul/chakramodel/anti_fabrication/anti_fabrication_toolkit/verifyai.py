"""
verifyai.py — ONE command that works for ANY project, forever.

FIRST TIME EVER:
    python verifyai.py init
    (sets your master password, only needed once on this machine)

REGISTER A NEW PROJECT/DATASET (needs the password):
    python verifyai.py add-project chakramodel colondb ^
        --dataset-root "M:\\chakramodel\\data\\cvc-colondb" ^
        --script "M:\\chakramodel\\src\\verify_strict.py" ^
        --section "CVC-ColonDB"

EVERY TIME AFTER THAT (no password needed, just this):
    python verifyai.py run chakramodel colondb

SEE WHAT'S REGISTERED:
    python verifyai.py list

If you don't remember the exact project/dataset names, just run
`verifyai.py list` first — it's read-only and safe.
"""

import os
import re
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.harness_core import (
    plant_multi_canary, run_live, verify, extract_section,
    sign_verdict, write_completion_card,
)
from core import registry
from core.activity_log import append_log, read_log, verify_log_integrity

VERDICTS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verdicts")


def cmd_init(args):
    registry.init_password()


def cmd_add_project(args):
    registry.add_project(
        args.project, args.dataset, args.dataset_root, args.script,
        section_label=args.section or "",
    )


def cmd_list(args):
    registry.list_all()


def cmd_log(args):
    if args.verify:
        verify_log_integrity()
    else:
        read_log(args.n)


def cmd_run(args):
    entry = registry.get_entry(args.project, args.dataset)
    dataset_root = entry["dataset_root"]
    script = entry["script"]
    label = entry.get("section_label", "")

    if not os.path.isdir(dataset_root):
        print(f"[VERIFY] FAIL: dataset root does not exist: {dataset_root}")
        sys.exit(1)
    if not os.path.isfile(script):
        print(f"[VERIFY] FAIL: script does not exist: {script}")
        sys.exit(1)

    pinned_hash = entry.get("script_sha256")
    if pinned_hash:
        from core.registry import _sha256_file
        current_hash = _sha256_file(script)
        if current_hash != pinned_hash:
            print("=" * 60)
            print("TAMPER DETECTED: the evaluation script has changed since it")
            print("was registered. Refusing to run an unreviewed script version.")
            print(f"  Pinned:  {pinned_hash[:16]}...")
            print(f"  Current: {current_hash[:16]}...")
            print("If this change is legitimate (you or a teammate improved the")
            print("script on purpose), review the diff yourself, then re-run:")
            print(f"  verifyai add-project {args.project} {args.dataset} "
                  f"--dataset-root \"{dataset_root}\" --script \"{script}\"")
            print("(requires the master password, on purpose).")
            print("=" * 60)
            sys.exit(1)

    print(f"[VERIFY] Project: {args.project} | Dataset: {args.dataset} ({label or 'whole script'})")
    print(f"[VERIFY] Dataset root: {dataset_root}")
    print(f"[VERIFY] Script: {script}")

    secret = plant_multi_canary(dataset_root)
    img_dir = os.path.join(dataset_root, "images")
    real_count = len([f for f in os.listdir(img_dir)
                       if f.lower().endswith((".png", ".jpg", ".jpeg"))])

    full_text, arrivals, elapsed, rc = run_live(script, extra_env={"VERIFY_NONCE": secret["nonce"]})
    print("[VERIFY] ---- captured stdout begins ----")
    print(full_text)
    print("[VERIFY] ---- captured stdout ends ----")

    section_text = extract_section(full_text, label) if label else full_text
    if label and not section_text:
        print(f"[VERIFY] FAIL: dataset section '{label}' never appeared in the output.")
        sys.exit(1)

    m = re.search(r"Total images found:\s*(\d+)", section_text)
    claimed = int(m.group(1)) if m else -1

    verdict = verify(full_text, arrivals, elapsed, secret, claimed, real_count,
                      images_per_sec_ceiling=args.images_per_sec_ceiling)
    signed = sign_verdict(verdict, secret["hmac_key"])

    claim = {
        "metric_name": args.metric_name,
        "dataset": args.dataset,
        "n_images_claimed": claimed,
        "script": script,
    }
    card_path, decision = write_completion_card(signed, claim, args.project, VERDICTS_ROOT)
    append_log(args.project, args.dataset, decision, card_path, verdict["findings"])

    print("\n" + "=" * 60)
    print(f"FINAL VERDICT for {args.project}/{args.dataset}:", "PASS" if verdict["pass"] else "FAIL")
    for line in verdict["findings"]:
        print(" -", line)
    print(f"Completion card ({decision}): {card_path}")
    print("Only ADMITTED cards may be cited anywhere.")
    print("=" * 60)

    sys.exit(0 if verdict["pass"] else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Set the master password (do this once, ever).")

    p_add = sub.add_parser("add-project", help="Register a project+dataset (needs password).")
    p_add.add_argument("project")
    p_add.add_argument("dataset")
    p_add.add_argument("--dataset-root", required=True)
    p_add.add_argument("--script", required=True)
    p_add.add_argument("--section", default="", help="Section banner text, only needed if one script covers multiple datasets.")

    sub.add_parser("list", help="Show all registered projects/datasets (no password needed).")

    p_log = sub.add_parser("log", help="Show recent verification history (no password needed).")
    p_log.add_argument("-n", type=int, default=20, help="How many recent entries to show.")
    p_log.add_argument("--verify", action="store_true",
                        help="Check the whole log's hash chain for tampering instead of printing entries.")

    p_run = sub.add_parser("run", help="Run verification for a registered project+dataset.")
    p_run.add_argument("project")
    p_run.add_argument("dataset")
    p_run.add_argument("--metric-name", default="Dice")
    p_run.add_argument("--images-per-sec-ceiling", type=float, default=15.0)

    args = ap.parse_args()
    {
        "init": cmd_init,
        "add-project": cmd_add_project,
        "list": cmd_list,
        "run": cmd_run,
        "log": cmd_log,
    }[args.command](args)


if __name__ == "__main__":
    main()
