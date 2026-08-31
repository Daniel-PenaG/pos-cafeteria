"""Comparación before/after con BD seed reproducible (120 ventas)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASELINE_COMMIT = os.getenv("PERF_BASELINE_COMMIT", "f2456e0")
REPO_ROOT = ROOT.parent


def _run_measure(label: str, repo_root: Path) -> list[dict]:
    env = os.environ.copy()
    env["PERF_LOG"] = "1"
    env["PERF_LOG_SQL"] = "1"
    env["DATABASE_URL"] = "sqlite:///:memory:"
    env["LOCAL_SEED_CATALOG"] = "false"
    script = repo_root / "scripts" / "_measure_endpoints_once.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--label", label],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise RuntimeError(f"Medición {label} falló (exit {proc.returncode})")
    rows = []
    for line in proc.stdout.strip().splitlines():
        if not line.startswith("ROW|"):
            continue
        _, endpoint, sql_s, ms_s = line.split("|", 3)
        rows.append(
            {"endpoint": endpoint, "sql_avg": float(sql_s), "time_avg_ms": float(ms_s)}
        )
    return rows


def main() -> int:
    current = ROOT
    baseline_dir = Path(tempfile.mkdtemp(prefix="pos-baseline-"))
    try:
        subprocess.run(
            ["git", "worktree", "add", str(baseline_dir), BASELINE_COMMIT],
            cwd=str(REPO_ROOT),
            check=True,
            capture_output=True,
            text=True,
        )
        (baseline_dir / "backend" / "scripts").mkdir(parents=True, exist_ok=True)
        shutil.copy(
            current / "scripts" / "_measure_endpoints_once.py",
            baseline_dir / "backend" / "scripts" / "_measure_endpoints_once.py",
        )
        (baseline_dir / "backend" / "tests").mkdir(parents=True, exist_ok=True)
        shutil.copy(
            current / "tests" / "seed_perf.py",
            baseline_dir / "backend" / "tests" / "seed_perf.py",
        )
        before = _run_measure("before", baseline_dir / "backend")
        after = _run_measure("after", current)
    finally:
        subprocess.run(
            ["git", "worktree", "remove", str(baseline_dir), "--force"],
            cwd=str(REPO_ROOT),
            capture_output=True,
        )

    after_map = {r["endpoint"]: r for r in after}
    print(
        f"{'Endpoint':<55} {'SQL antes':>8} {'SQL desp':>8} {'ms antes':>9} {'ms desp':>9} {'Reduc%':>8}"
    )
    print("-" * 110)
    for b in before:
        ep = b["endpoint"]
        a = after_map.get(ep, {"sql_avg": 0, "time_avg_ms": 0})
        sql_red = round((1 - a["sql_avg"] / b["sql_avg"]) * 100, 1) if b["sql_avg"] else 0.0
        time_red = (
            round((1 - a["time_avg_ms"] / b["time_avg_ms"]) * 100, 1) if b["time_avg_ms"] else 0.0
        )
        reduc = max(sql_red, time_red)
        print(
            f"{ep:<55} {b['sql_avg']:>8.1f} {a['sql_avg']:>8.1f} "
            f"{b['time_avg_ms']:>9.2f} {a['time_avg_ms']:>9.2f} {reduc:>7.1f}%"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
