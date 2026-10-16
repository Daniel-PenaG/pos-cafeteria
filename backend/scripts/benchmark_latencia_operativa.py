"""Medición comparable base vs optimizado (PostgreSQL desechable).

Setup de escenario fuera de SQL y cronómetro en ambas ramas (mismo worker).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
WARMUP = 3
RUNS = 10
BASELINE_COMMIT = "e648e325dea25d033a4c152f2b706a5b0b54c28a"
DEFAULT_ONLY = ""

INVALID_PRIOR = {
    "POST confirmar comanda (10 líneas) sql_p50=582": "Incluía prep de 10 líneas dentro del contador SQL",
    "POST confirmar comanda (10 líneas) sql_p50=203": "Incluía prep de 10 líneas dentro del contador SQL",
    "confirmar_10_lineas sql_p50=572": "Medición contaminada (prep + endpoint)",
    "confirmar_10_lineas sql_p50=413": "Medición contaminada (prep + endpoint)",
    "cobrar_1_linea sql_p95=173ms baseline": "Prep mezclada con POST en algunas corridas antiguas",
}


def _git_commit(cwd: Path) -> str:
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout.strip()


def _pg_info(db_url: str) -> dict:
    if not db_url.startswith("postgresql"):
        return {"engine": "sqlite", "version": "n/a"}
    engine = create_engine(db_url)
    with engine.connect() as conn:
        ver = conn.execute(text("SHOW server_version")).scalar()
    engine.dispose()
    m = re.match(r"(\d+(?:\.\d+)*)", ver or "")
    return {"engine": "postgresql", "version": ver, "major": m.group(1) if m else None}


def _run_in_backend(backend_root: Path, env: dict) -> dict:
    env = {**os.environ, **env}
    env["PYTHONPATH"] = str(backend_root)
    proc = subprocess.run(
        [sys.executable, str(backend_root / "scripts" / "_benchmark_latencia_worker.py")],
        cwd=str(backend_root),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise RuntimeError(f"Worker falló (exit {proc.returncode})")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _scenario_rows(scenarios: dict) -> list:
    rows = []
    for sid, stats in scenarios.items():
        rows.append({"escenario": sid, **stats})
    return rows


def _print_compare(before: dict, after: dict) -> None:
    keys = after.get("scenarios", {})
    print(
        f"\n{'Escenario':<40} {'p50 ms b/o':>16} {'p95 ms b/o':>16} {'SQL50 b/o':>14} {'bytes50 b/o':>14}"
    )
    print("-" * 102)
    for sid in keys:
        b = before.get("scenarios", {}).get(sid, {})
        a = keys[sid]
        print(
            f"{sid:<40} "
            f"{b.get('p50_ms', 0):>6.1f}/{a.get('p50_ms', 0):<6.1f} "
            f"{b.get('p95_ms', 0):>6.1f}/{a.get('p95_ms', 0):<6.1f} "
            f"{b.get('sql_p50', 0):>5.0f}/{a.get('sql_p50', 0):<5.0f} "
            f"{b.get('bytes_p50', 0):>5.0f}/{a.get('bytes_p50', 0):<5.0f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", action="store_true", help="Baseline + rama actual")
    parser.add_argument("--write-docs", action="store_true", default=True)
    parser.add_argument("--runs", type=int, default=int(os.getenv("RUNS", str(RUNS))))
    parser.add_argument("--only", default=os.getenv("BENCHMARK_ONLY", DEFAULT_ONLY))
    args = parser.parse_args()
    runs = max(1, args.runs)

    db_url = os.getenv("PERF_DATABASE_URL") or os.getenv("POSTGRES_TEST_URL")
    if not db_url or not db_url.startswith("postgresql"):
        print("PERF_DATABASE_URL (PostgreSQL) es obligatorio para comparación válida.", file=sys.stderr)
        return 1

    base_commit = os.getenv("PERF_BASELINE_COMMIT", BASELINE_COMMIT)
    worker_src = ROOT / "scripts" / "_benchmark_latencia_worker.py"
    seed_src = ROOT / "tests" / "seed_perf.py"
    if not worker_src.is_file():
        print("Falta _benchmark_latencia_worker.py", file=sys.stderr)
        return 1

    pg = _pg_info(db_url)
    common_env = {
        "PERF_LOG": "1",
        "PERF_LOG_SQL": "1",
        "PERF_LOG_SQL_SIGNATURE": "0",
        "DATABASE_URL": db_url,
        "LOCAL_SEED_CATALOG": "false",
        "WARMUP": str(WARMUP),
        "RUNS": str(runs),
    }
    if args.only:
        common_env["BENCHMARK_ONLY"] = args.only

    doc = {
        "methodology": {
            "warmup_runs": WARMUP,
            "samples_per_scenario": runs,
            "sql_signature_profiler": False,
            "setup_outside_sql_and_timer": True,
            "seed": "tests/seed_perf.seed_perf_db(num_ventas=120)",
            "worker": "backend/scripts/_benchmark_latencia_worker.py",
            "note": "Solo tiempo/SQL del endpoint medido; prep en setup_fn.",
        },
        "postgresql": pg,
        "database_url_redacted": re.sub(r"://([^:@/]+):([^@/]+)@", r"://\\1:***@", db_url),
        "invalid_prior_measurements": INVALID_PRIOR,
        "sqlite_reference": "docs/sql_profile_operaciones.json (TestClient, regresión local)",
    }

    if args.compare:
        baseline_dir = Path(tempfile.mkdtemp(prefix="pos-perf-base-"))
        try:
            subprocess.run(
                ["git", "worktree", "add", "--detach", str(baseline_dir), base_commit],
                cwd=str(REPO),
                check=True,
                capture_output=True,
                text=True,
            )
            b_backend = baseline_dir / "backend"
            (b_backend / "scripts").mkdir(parents=True, exist_ok=True)
            (b_backend / "tests").mkdir(parents=True, exist_ok=True)
            shutil.copy(worker_src, b_backend / "scripts" / "_benchmark_latencia_worker.py")
            if seed_src.is_file():
                shutil.copy(seed_src, b_backend / "tests" / "seed_perf.py")

            b_commit = _git_commit(baseline_dir)
            o_commit = _git_commit(REPO)

            before = _run_in_backend(
                b_backend,
                {**common_env, "PERF_GIT_COMMIT": b_commit},
            )
            after = _run_in_backend(
                ROOT,
                {**common_env, "PERF_GIT_COMMIT": o_commit},
            )

            doc["baseline"] = {
                "commit": before.get("commit") or b_commit,
                "commit_short": (before.get("commit") or b_commit)[:12],
                "label": "e648e325 base latencia",
                "scenarios": _scenario_rows(before.get("scenarios", {})),
            }
            doc["optimized"] = {
                "commit": after.get("commit") or o_commit,
                "commit_short": (after.get("commit") or o_commit)[:12],
                "label": "performance/latencia-operativa-pos",
                "scenarios": _scenario_rows(after.get("scenarios", {})),
            }
            doc["comparison_valid"] = True
            doc["comparison_note"] = (
                "Mismo worker, seed, PG, warmup y muestras en baseline y optimizado. "
                "No usar mejoras % de mediciones marcadas en invalid_prior_measurements."
            )

            _print_compare(before, after)

            if args.write_docs:
                if args.only:
                    safe = args.only.replace(",", "_")
                    out = REPO / "docs" / f"benchmark_{safe}_{runs}m.json"
                else:
                    out = REPO / "docs" / "benchmark_latencia_operativa.json"
                out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"\nJSON: {out}")
        finally:
            subprocess.run(
                ["git", "worktree", "remove", str(baseline_dir), "--force"],
                cwd=str(REPO),
                capture_output=True,
            )
    else:
        o_commit = _git_commit(REPO)
        after = _run_in_backend(ROOT, {**common_env, "PERF_GIT_COMMIT": o_commit})
        doc["optimized_only"] = {
            "commit": after.get("commit") or o_commit,
            "scenarios": _scenario_rows(after.get("scenarios", {})),
        }
        print(json.dumps(doc, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
