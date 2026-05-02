import argparse
import csv
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from io_utils.file_selector import select_file
from scheduling_intelligent_ils.beam_search_scheduler import BeamSearchScheduler
from scheduling_intelligent_ils.common import (
    load_candidate_solution,
    load_instance,
    save_solution,
)
from scheduling_intelligent_ils.intelligent_ils_scheduler import AdaptiveHybridILSScheduler
from scheduling_intelligent_ils.smart_tv_scheduler_scoreboost import SmartTVSchedulerScoreBoost

INPUT_DIR = PROJECT_ROOT / "data" / "input"
BEAM_DIR = PROJECT_ROOT / "data" / "solutions" / "constructiveapproach"
DPS_DIR = PROJECT_ROOT / "data" / "solutions" / "dp_segmenting"
ILS_DIR = PROJECT_ROOT / "data" / "solutions" / "intelligent_ils"


def instance_name(instance_path: Path) -> str:
    stem = instance_path.stem
    if stem.endswith("_input"):
        return stem[: -len("_input")]
    return stem


def matches_instance(seed_path: Path, instance_path: Path) -> bool:
    seed_stem = seed_path.stem
    names = {instance_path.stem, instance_name(instance_path)}

    return any(
        seed_stem == name or seed_stem.startswith(f"{name}_")
        for name in names
    )


def best_existing_seed(instance, instance_path: Path, directory: Path, source: str):
    best_path = None
    best_solution = None
    errors = []

    for seed_path in sorted(directory.glob("*.json")):
        if not matches_instance(seed_path, instance_path):
            continue

        try:
            solution = load_candidate_solution(instance, seed_path, source)
        except Exception as exc:
            errors.append(f"{seed_path.name}: {exc}")
            continue

        if best_solution is None or solution.total_score > best_solution.total_score:
            best_path = seed_path
            best_solution = solution

    return best_path, best_solution, errors


def generate_beam_seed(instance, name: str, verbose: bool) -> Path:
    solver = BeamSearchScheduler(instance, verbose=verbose)
    solution = solver.generate_solution()
    output_path = BEAM_DIR / f"{name}_output_beamsearchscheduler_{int(solution.total_score)}.json"
    return save_solution(solution, output_path)


def generate_dps_seed(instance, name: str, verbose: bool) -> Path:
    solver = SmartTVSchedulerScoreBoost(instance, verbose=verbose)
    solution = solver.generate_solution()
    output_path = DPS_DIR / f"{name}_output_dpsegmenting_{int(solution.total_score)}.json"
    return save_solution(solution, output_path)


def ensure_seed(
    instance,
    instance_path: Path,
    directory: Path,
    source: str,
    generator,
    regenerate: bool,
    generate_missing: bool,
    verbose: bool,
):
    name = instance_name(instance_path)
    seed_path, solution, errors = best_existing_seed(instance, instance_path, directory, source)

    if regenerate or (solution is None and generate_missing):
        generated_path = generator(instance, name, verbose)
        if verbose:
            print(f"[seed] Generated {generated_path}")
        seed_path, solution, errors = best_existing_seed(instance, instance_path, directory, source)

    if solution is None:
        details = "; ".join(errors[:3])
        raise FileNotFoundError(f"No valid {source} seed found for {name}. {details}")

    return seed_path, solution


def run_instance(
    instance_path: Path,
    regenerate_seeds: bool,
    generate_missing: bool,
    seeds_only: bool,
    max_iterations: int | None,
    verbose: bool,
):
    started = time.perf_counter()
    name = instance_name(instance_path)
    row = {
        "instance": name,
        "status": "started",
        "beam_seed": "",
        "beam_score": "",
        "dps_seed": "",
        "dps_score": "",
        "best_seed": "",
        "final_score": "",
        "improvement": "",
        "time_seconds": "",
        "output_file": "",
        "message": "",
    }

    try:
        instance = load_instance(instance_path)

        beam_path, beam_seed = ensure_seed(
            instance,
            instance_path,
            BEAM_DIR,
            "beam_existing_seed",
            generate_beam_seed,
            regenerate_seeds,
            generate_missing,
            verbose,
        )
        dps_path, dps_seed = ensure_seed(
            instance,
            instance_path,
            DPS_DIR,
            "dps_existing_seed",
            generate_dps_seed,
            regenerate_seeds,
            generate_missing,
            verbose,
        )

        best_seed = "beam_search" if beam_seed.total_score >= dps_seed.total_score else "dp_segmenting"
        initial_best_score = max(beam_seed.total_score, dps_seed.total_score)

        row.update(
            {
                "beam_seed": str(beam_path.relative_to(PROJECT_ROOT)),
                "beam_score": beam_seed.total_score,
                "dps_seed": str(dps_path.relative_to(PROJECT_ROOT)),
                "dps_score": dps_seed.total_score,
                "best_seed": best_seed,
            }
        )

        if seeds_only:
            row["status"] = "seeds_ok"
            return row

        solver = AdaptiveHybridILSScheduler(
            instance,
            max_iterations=max_iterations,
            verbose=verbose,
            beam_seed_path=beam_path,
            dps_seed_path=dps_path,
        )
        solution = solver.generate_solution()

        output_path = ILS_DIR / f"{name}_output_intelligentils_{int(solution.total_score)}.json"
        save_solution(solution, output_path)

        row.update(
            {
                "status": "ok",
                "final_score": solution.total_score,
                "improvement": solution.total_score - initial_best_score,
                "output_file": str(output_path.relative_to(PROJECT_ROOT)),
            }
        )

    except Exception as exc:
        row["status"] = "error"
        row["message"] = str(exc)

    finally:
        row["time_seconds"] = round(time.perf_counter() - started, 2)

    return row


def write_summary(rows: list[dict]) -> Path:
    ILS_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = ILS_DIR / "summary_intelligent_ils_from_existing_seeds.csv"
    fieldnames = [
        "instance",
        "status",
        "beam_seed",
        "beam_score",
        "dps_seed",
        "dps_score",
        "best_seed",
        "final_score",
        "improvement",
        "time_seconds",
        "output_file",
        "message",
    ]

    with summary_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return summary_path


def parse_args():
    parser = argparse.ArgumentParser(description="Run the hybrid Intelligent ILS pipeline.")
    parser.add_argument("--all", action="store_true", help="Run every JSON instance in data/input.")
    parser.add_argument("--instance", type=Path, help="Run one specific input JSON file.")
    parser.add_argument("--seeds-only", action="store_true", help="Generate/check Beam and DP-S seeds only.")
    parser.add_argument("--regenerate-seeds", action="store_true", help="Run Beam and DP-S even if seeds exist.")
    parser.add_argument("--no-generate-missing", action="store_true", help="Fail instead of generating missing seeds.")
    parser.add_argument("--max-iterations", type=int, default=None, help="Override ILS iterations.")
    parser.add_argument("--verbose", action="store_true", help="Print detailed algorithm progress.")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.all:
        instance_paths = sorted(INPUT_DIR.glob("*.json"))
    elif args.instance:
        instance_paths = [args.instance]
    else:
        selected = select_file(str(INPUT_DIR))
        if not selected:
            print("No file selected. Exiting program...")
            return
        instance_paths = [Path(selected)]

    rows = []
    generate_missing = not args.no_generate_missing

    for instance_path in instance_paths:
        print(f"\n=== {instance_name(instance_path)} ===")
        row = run_instance(
            instance_path=instance_path,
            regenerate_seeds=args.regenerate_seeds,
            generate_missing=generate_missing,
            seeds_only=args.seeds_only,
            max_iterations=args.max_iterations,
            verbose=args.verbose,
        )
        rows.append(row)

        if row["status"] in {"ok", "seeds_ok"}:
            print(
                f"{row['status']}: beam={row['beam_score']} | "
                f"dp-s={row['dps_score']} | final={row['final_score']}"
            )
        else:
            print(f"error: {row['message']}")

    summary_path = write_summary(rows)
    print(f"\nSummary saved to: {summary_path}")


if __name__ == "__main__":
    main()
