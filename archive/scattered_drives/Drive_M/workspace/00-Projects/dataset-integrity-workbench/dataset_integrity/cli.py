from __future__ import annotations
import argparse, json, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from .core import Source, build_manifest, compare_manifests, duplicate_groups, inspect_file
from .persistence import Store
from .release import QualityContract, ReleaseCandidate, default_metadata
from .credentials import (CredentialProfile, WindowsCredentialManagerProvider,
                          build_rotation_plan, parse_profiles, verify_https_source, verify_profile)
from .reporting import configured_models
from .connectors import inspect_target
from .inventory import COMMON_EXCLUDED_DIRS, inventory_roots
from .analyzer import export_report, scan_filesystem
from .datasets import discover_dataset
from .integrations import OptionalDependencyError, capability
import hashlib

def now(): return datetime.now(timezone.utc).isoformat()
def emit(data, human=False):
    if human:
        print(f"{data.get('status','PASS')}: {data.get('source', '')} ({len(data.get('records', []))} files)")
        for k in ("added","removed","changed","duplicates","errors"):
            if data.get(k): print(f"  {k}: {len(data[k])}")
    else: print(json.dumps(data, sort_keys=True, indent=2))

def main(argv=None):
    p = argparse.ArgumentParser(prog="dataset-integrity")
    p.add_argument("--db", default="dataset-integrity.sqlite")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("register"); r.add_argument("name"); r.add_argument("root"); r.add_argument("--type", default="filesystem")
    r.add_argument("--license", help="declared license or terms reference")
    r.add_argument("--credential-profile", help="redacted credential profile name (never a secret)")
    si = sub.add_parser("source-inspect", help="inspect one explicit source target (metadata only)")
    si.add_argument("source")
    si.add_argument("--network", action="store_true", help="opt in to one HTTPS HEAD request")
    ct = sub.add_parser("connector-test", help="test one explicit source connector")
    ct.add_argument("source")
    ct.add_argument("--network", action="store_true", help="opt in to one HTTPS HEAD request")
    s = sub.add_parser("scan"); s.add_argument("source"); s.add_argument("--run-id"); s.add_argument("--resume", action="store_true"); s.add_argument("--allow-incomplete", action="store_true"); s.add_argument("--human", action="store_true")
    c = sub.add_parser("compare"); c.add_argument("source"); c.add_argument("--manifest", help="current manifest SHA-256 (defaults to latest)"); c.add_argument("--prior", help="prior manifest SHA-256 (defaults to previous)"); c.add_argument("--human", action="store_true")
    cr = sub.add_parser("create-release", aliases=["create"]); cr.add_argument("source"); cr.add_argument("--manifest"); cr.add_argument("--contract", default="default"); cr.add_argument("--contract-version", default="1"); cr.add_argument("--max-errors", type=int, default=0); cr.add_argument("--max-duplicates", type=int); cr.add_argument("--min-files", type=int, default=0); cr.add_argument("--allow-incomplete", action="store_true"); cr.add_argument("--seed", type=int, default=0); cr.add_argument("--code-version", default="unknown"); cr.add_argument("--config-version", default="unknown"); cr.add_argument("--plugin-version", action="append", default=[]); cr.add_argument("--evidence-dir")
    ck = sub.add_parser("check-release", aliases=["check"]); ck.add_argument("candidate"); ck.add_argument("--evidence-dir")
    pr = sub.add_parser("promote-release", aliases=["promote"]); pr.add_argument("candidate")
    rj = sub.add_parser("reject-release", aliases=["reject"]); rj.add_argument("candidate")
    li = sub.add_parser("inspect-lineage", aliases=["lineage"], help="inspect append-only release evidence lineage")
    li.add_argument("target", nargs="?")
    li.add_argument("--release")
    li.add_argument("--candidate")
    lp = sub.add_parser("list-profiles", help="list credential profile metadata (never keys)")
    lp.add_argument("--profile", action="append", default=[], metavar="NAME=TARGET")
    tp = sub.add_parser("test-profile", help="retrieve and verify a credential profile")
    tp.add_argument("name")
    tp.add_argument("--profile", action="append", default=[], metavar="NAME=TARGET")
    tp.add_argument("--verify-network", action="store_true")
    tp.add_argument("--source-target", help="explicit target for opt-in network verification")
    rot = sub.add_parser(
        "credential-plan",
        help="print a non-secret four-slot rotation plan; never retrieves or saves keys",
    )
    rot.add_argument(
        "--profile", action="append", default=[], metavar="NAME=TARGET",
        help="profile reference; repeat up to four times (metadata only)",
    )
    rot.add_argument(
        "--model", action="append", default=[],
        help="allowed reporting model name; repeatable and metadata-only",
    )
    models = sub.add_parser(
        "gemini-models",
        help="show configured model names without contacting Gemini or reading keys",
    )
    models.add_argument("--model", action="append", default=[], help="model name; repeatable")
    inv = sub.add_parser("inventory", aliases=["validate"], help="read-only inventory of explicit roots")
    inv.add_argument("roots", nargs="+")
    inv.add_argument("--human", action="store_true")
    inv.add_argument("--progress", action="store_true", help="write deterministic progress to stderr")
    inv.add_argument("--report", help="write the JSON report outside the inspected roots")
    inv.add_argument("--evidence-dir", help="write evidence files only for complete runs")
    inv.add_argument("--allow-incomplete", action="store_true",
                     help="allow evidence output when inspection is incomplete")
    inv.add_argument("--exclude-dir", action="append", default=[], metavar="NAME",
                     help="exclude matching directory components (repeatable; opt-in)")
    inv.add_argument("--exclude-common", action="store_true",
                     help="exclude common VCS, environment, build, cache, and checkpoint directories")
    inv.add_argument("--image-validator", choices=("stdlib", "pillow"), default="stdlib",
                     help="optional image validation mode; pillow requires an already-installed Pillow")
    analyze = sub.add_parser("analyze", help="resumable SQLite-backed filesystem analysis")
    analyze.add_argument("root")
    analyze.add_argument("--run-id")
    analyze.add_argument("--workers", type=int, default=4)
    analyze.add_argument("--exclude-dir", action="append", default=[])
    analyze.add_argument("--export")
    analyze.add_argument("--format", choices=("json", "csv", "text"), default="json")
    analyze.add_argument("--stop-after", type=int)
    discover = sub.add_parser("discover", help="discover and validate a dataset layout")
    discover.add_argument("root")
    integ = sub.add_parser("capability", help="report optional integration availability")
    integ.add_argument("name", choices=("cleanvision", "fiftyone", "datumaro", "gemini"))
    args = p.parse_args(argv)
    if args.command == "credential-plan":
        profiles = parse_profiles(args.profile)
        print(json.dumps(build_rotation_plan(profiles, args.model).as_dict(),
                         sort_keys=True, indent=2))
        return 0
    if args.command == "gemini-models":
        print(json.dumps({"models": list(configured_models(args.model)),
                          "gemini_contacted": False, "credentials_accessed": False},
                         sort_keys=True, indent=2))
        return 0
    if args.command == "analyze":
        result = scan_filesystem(args.root, args.db, args.run_id, args.workers,
                                 args.exclude_dir, args.stop_after).as_dict()
        if args.export:
            export_report(result, args.export, args.format)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0 if result["complete"] else 2
    if args.command == "discover":
        print(json.dumps(discover_dataset(args.root), sort_keys=True, indent=2))
        return 0
    if args.command == "capability":
        print(json.dumps(capability(args.name), sort_keys=True, indent=2))
        return 0
    if args.command in ("inventory", "validate"):
        excluded_dirs = set(args.exclude_dir)
        if args.exclude_common:
            excluded_dirs.update(COMMON_EXCLUDED_DIRS)
        result = inventory_roots(args.roots, progress=args.progress, exclude_dirs=excluded_dirs,
                                 image_validator=args.image_validator)
        if args.report:
            Path(args.report).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        if args.evidence_dir:
            if not result["complete"] and not args.allow_incomplete:
                print("incomplete inventory: evidence output skipped (use --allow-incomplete)", file=sys.stderr)
            else:
                _write_inventory_evidence(args.evidence_dir, result)
        if args.human:
            summary = result["summary"]
            status = "PASS" if result["complete"] and not summary["errors"] else ("WARN" if result["complete"] else "FAIL")
            print(f"{status}: {summary['files']} files across {len(result['roots'])} roots")
            print(f"  modalities: {json.dumps(summary['modalities'], sort_keys=True)}")
            print(f"  annotations: {summary['annotations']}; duplicates: {summary['duplicate_groups']}; errors: {summary['errors']}")
            print(f"  excluded: {summary['excluded_files']} files in {summary['excluded_directories']} directories")
            print(f"  manifest: {result['manifest']['sha256'] if result['manifest'] else 'incomplete'}")
        else:
            print(json.dumps(result, sort_keys=True, indent=2))
        if not result["complete"]:
            return 2
        return 1 if result["summary"]["errors"] else 0
    store = Store(args.db)
    try:
        if args.command == "list-profiles":
            profiles = parse_profiles(args.profile)
            provider = WindowsCredentialManagerProvider(profiles)
            for profile in provider.list_profiles():
                store.record_credential_profile(profile.name, profile.provider, profile.target)
            print(json.dumps([{"profile": p.name, "provider": p.provider, "target": p.target}
                              for p in provider.list_profiles()], sort_keys=True, indent=2))
            return 0
        if args.command == "test-profile":
            profiles = {p.name: p for p in parse_profiles(args.profile)}
            if args.name not in profiles:
                raise ValueError("profile must be supplied as NAME=TARGET")
            result = verify_profile(provider := WindowsCredentialManagerProvider(profiles.values()),
                                    profiles[args.name], network=args.verify_network,
                                    source_target=args.source_target,
                                    network_verifier=verify_https_source if args.verify_network else None)
            store.record_credential_profile(profiles[args.name].name, profiles[args.name].provider,
                                            profiles[args.name].target)
            print(json.dumps(result, sort_keys=True, indent=2))
            return 0
        if args.command == "register":
            metadata = {}
            if args.license:
                metadata["license_terms"] = {"reference": args.license}
            if args.credential_profile:
                metadata["credential_profile"] = args.credential_profile
            root = str(Path(args.root).resolve()) if args.type in ("filesystem", "archive") else args.root
            store.register(Source(args.name, root, args.type, metadata))
            print(json.dumps({"status":"PASS","source":args.name}))
            return 0
        if args.command in ("source-inspect", "connector-test"):
            source = store.source(args.source)
            observation = inspect_target(source.source_type, source.root, network=args.network,
                                         metadata=source.metadata)
            observation_id = store.record_connector_metadata(source.name, observation)
            result = observation.as_dict()
            result.update({"status": "PASS" if observation.exists is not False else "FAIL",
                           "source": source.name, "observation_id": observation_id,
                           "operation": args.command})
            print(json.dumps(result, sort_keys=True, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.command in ("inspect-lineage", "lineage"):
            target = args.target or args.release or args.candidate
            if not target:
                raise ValueError("a release or candidate id is required")
            print(json.dumps(store.lineage_for(target), sort_keys=True, indent=2))
            return 0
        if args.command in ("create-release", "create"):
            source = store.source(args.source)
            manifest = store.manifest(args.manifest) if args.manifest else store.latest_manifest(source.name)
            if not manifest:
                raise KeyError("no manifest")
            if not manifest.complete and not args.allow_incomplete:
                raise ValueError("incomplete manifests cannot be released without --allow-incomplete")
            plugins = dict(item.split("=", 1) for item in args.plugin_version if "=" in item)
            contract = QualityContract(args.contract, args.contract_version, not args.allow_incomplete,
                                       args.max_errors, args.max_duplicates, args.min_files)
            candidate = ReleaseCandidate.create(manifest, contract, default_metadata(
                args.seed, args.code_version, args.config_version, plugins))
            store.save_candidate(candidate)
            result = candidate.as_dict()
            if args.evidence_dir:
                _write_evidence(args.evidence_dir, result, store, candidate.candidate_id)
            print(json.dumps(result, sort_keys=True, indent=2))
            return 0 if candidate.quality.passed else 1
        if args.command in ("check-release", "check"):
            candidate = store.candidate(args.candidate)
            result = candidate.as_dict()
            if args.evidence_dir:
                _write_evidence(args.evidence_dir, result, store, candidate.candidate_id)
            print(json.dumps(result, sort_keys=True, indent=2))
            return 0 if candidate.quality.passed else 1
        if args.command in ("promote-release", "reject-release", "promote", "reject"):
            candidate = store.candidate(args.candidate)
            if args.command in ("promote-release", "promote") and not candidate.quality.passed:
                raise ValueError("quality contract has not passed")
            state = "promoted" if args.command in ("promote-release", "promote") else "rejected"
            candidate = store.set_candidate_state(candidate.candidate_id, state)
            store.save_release(candidate.candidate_id, candidate, state)
            print(json.dumps(candidate.as_dict(), sort_keys=True, indent=2))
            return 0
        if args.command == "scan":
            source = store.source(args.source)
            run_id = args.run_id or str(uuid.uuid4())
            store.start_run(run_id, source.name, now())
            records = store.run_records(run_id) if args.resume else []
            seen = {r.path for r in records}
            try:
                for path in sorted(Path(source.root).rglob("*")):
                    if path.is_file() and path.relative_to(source.root).as_posix() not in seen:
                        record = inspect_file(path, source.root); store.save_record(run_id, record); records.append(record)
                complete = True
            except (KeyboardInterrupt, OSError) as exc:
                complete = False; print(f"scan incomplete: {exc}", file=sys.stderr)
            store.finish_run(run_id, now(), "complete" if complete else "incomplete")
            manifest = build_manifest(source.name, records, now(), complete, run_id)
            if complete or args.allow_incomplete: store.save_manifest(manifest)
            result = manifest.as_dict(); result.update({"status": "PASS" if complete and not any(r.errors for r in records) else ("WARN" if complete else "FAIL"), "duplicates": duplicate_groups(records), "errors": [r.path for r in records if r.errors]})
            emit(result, args.human); return 0 if complete else 2
        source = store.source(args.source)
        current = store.manifest(args.manifest) if args.manifest else store.latest_manifest(source.name)
        prior = store.manifest(args.prior) if args.prior else (store.previous_manifest(source.name, current.manifest_sha256) if current else None)
        result = compare_manifests(current, prior) if current and prior else {"status":"WARN","error":"two manifests are required"}
        if current:
            result["source"] = current.source
            result["records"] = [r.as_dict() for r in current.records]
        emit(result, args.human); return 0 if result["status"] == "PASS" else 1
    finally: store.close()


def _write_evidence(directory: str, payload: dict, store: Optional[Store] = None,
                    target_id: Optional[str] = None) -> None:
    """Write a portable bundle without relying on filesystem traversal order."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    (root / "release.json").write_text(body, encoding="utf-8")
    (root / "checks.json").write_text(json.dumps(payload.get("quality", {}), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    (root / "bundle.sha256").write_text(digest + "\n", encoding="ascii")
    if store and target_id:
        store.record_evidence_artifact(str(root.resolve()), target_id, digest, str(root.resolve()))


def _write_inventory_evidence(directory: str, payload: dict) -> None:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    (root / "inventory.json").write_text(body, encoding="utf-8")
    manifest = payload.get("manifest")
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n",
                                         encoding="utf-8")
    (root / "evidence.sha256").write_text(hashlib.sha256(body.encode()).hexdigest() + "\n",
                                          encoding="ascii")
