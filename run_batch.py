#!/usr/bin/env python3
"""
Batch runner: executes Simulated Annealing (SA) and SA-Cutoff on every
instance that has at least one initial solution available.

Usage:
    python run_batch.py

Results are saved to:
    data/solutions/simulated_annealing/
    data/solutions/simulated_annealing_cutoff/

A summary table is printed to the terminal when all instances finish.
"""

import json
import random
import time
from pathlib import Path

from io_utils.instance_parser import InstanceParser
from io_utils.initial_solution_parser import SolutionParser
from evaluators.base_evaluator import BaseEvaluator
from models.solution.solution import Solution
from utils.validator import validate_schedule_against_instance

from solvers.simulated_annealing_solver import SimulatedAnnealingSolver
from solvers.simulated_annealing_cutoff_solver import SimulatedAnnealingCutoffSolver

import config.simulated_annealing_config as sa_config
import config.simulated_annealing_cutoff_config as sa_cutoff_config


INPUT_DIR = Path("data/input")
SOLUTION_DIRS = [
    Path("data/solutions/constructiveapproach"),
    Path("data/solutions/dp_segmenting"),
]


# -------------------------------------------------------
# Helpers (mirrored from main.py)
# -------------------------------------------------------

def save_solution(schedule, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scheduled_programs": [
            {"program_id": p.program_id, "channel_id": p.channel_id,
             "start": p.start, "end": p.end}
            for p in schedule
        ]
    }
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)


def build_solution(instance, schedule) -> Solution:
    evaluator = BaseEvaluator(instance)
    selected_ids = {p.program_id for p in schedule}
    unselected_ids = [
        prog.program_id
        for ch in instance.channels
        for prog in ch.programs
        if prog.program_id not in selected_ids
    ]
    return Solution(evaluator=evaluator, selected=schedule, unselected_ids=unselected_ids)


def load_best_initial_solution(instance, instance_name: str):
    """Return the Solution with the highest fitness across all solution dirs."""
    best_sol = None
    best_fitness = float("-inf")

    for directory in SOLUTION_DIRS:
        if not directory.exists():
            continue
        for file_path in directory.glob(f"{instance_name}*.json"):
            try:
                schedule = SolutionParser(file_path).parse()
                validate_schedule_against_instance(schedule, instance)
                sol = build_solution(instance, schedule)
                if sol.fitness > best_fitness:
                    best_fitness = sol.fitness
                    best_sol = sol
            except Exception:
                continue

    return best_sol


# -------------------------------------------------------
# Adaptive parameters based on instance size
# -------------------------------------------------------

# Time budget per solver per instance (seconds)
MAX_TIME_PER_INSTANCE = 120

def _adaptive_ns(instance) -> int:
    """Scale Ns down for large instances so each run stays within time budget."""
    total_programs = sum(len(c.programs) for c in instance.channels)
    if total_programs > 3000:
        return 10
    if total_programs > 1000:
        return 30
    return sa_config.NS


# -------------------------------------------------------
# Per-solver runners
# -------------------------------------------------------

def run_sa(instance, solution: Solution, instance_name: str, seed: int) -> dict:
    ns = _adaptive_ns(instance)
    solver = SimulatedAnnealingSolver(
        solution=solution,
        t0=sa_config.T0,
        tf=sa_config.TF,
        alpha=sa_config.ALPHA,
        ns=ns,
        max_shift=sa_config.MAX_SHIFT,
        max_time=MAX_TIME_PER_INSTANCE,
        seed=seed,
    )
    t0 = time.time()
    best = solver.solve(instance)
    elapsed = time.time() - t0

    output_path = (
        Path("data/solutions/simulated_annealing")
        / instance_name
        / f"{instance_name}_sa_{int(best.fitness)}.json"
    )
    save_solution(best.selected.scheduled_programs, output_path)

    return {
        "solver": "SA",
        "instance": instance_name,
        "initial": solution.fitness,
        "score": best.fitness,
        "improvement": best.fitness - solution.fitness,
        "time_s": elapsed,
        "saved": output_path,
    }


def run_sa_cutoff(instance, solution: Solution, instance_name: str, seed: int) -> dict:
    ns = _adaptive_ns(instance)
    solver = SimulatedAnnealingCutoffSolver(
        solution=solution,
        t0=sa_cutoff_config.T0,
        tf=sa_cutoff_config.TF,
        alpha=sa_cutoff_config.ALPHA,
        ns=ns,
        na=sa_cutoff_config.NA,
        max_shift=sa_cutoff_config.MAX_SHIFT,
        max_time=MAX_TIME_PER_INSTANCE,
        seed=seed,
    )
    t0 = time.time()
    best = solver.solve(instance)
    elapsed = time.time() - t0

    output_path = (
        Path("data/solutions/simulated_annealing_cutoff")
        / instance_name
        / f"{instance_name}_sa_cutoff_{int(best.fitness)}.json"
    )
    save_solution(best.selected.scheduled_programs, output_path)

    return {
        "solver": "SA-Cutoff",
        "instance": instance_name,
        "initial": solution.fitness,
        "score": best.fitness,
        "improvement": best.fitness - solution.fitness,
        "time_s": elapsed,
        "saved": output_path,
    }


# -------------------------------------------------------
# Summary table
# -------------------------------------------------------

def print_summary(results: list):
    print("\n" + "=" * 80)
    print("BATCH RUN SUMMARY")
    print("=" * 80)
    header = f"{'Instance':<25} {'Solver':<12} {'Initial':>10} {'Score':>10} {'Improvement':>12} {'Time(s)':>8}"
    print(header)
    print("-" * 80)
    for r in results:
        print(
            f"{r['instance']:<25} {r['solver']:<12} "
            f"{r['initial']:>10.2f} {r['score']:>10.2f} "
            f"{r['improvement']:>+12.2f} {r['time_s']:>8.1f}"
        )
    print("=" * 80)


# -------------------------------------------------------
# Main
# -------------------------------------------------------

def main():
    seed = int(time.time() * 1000) % (2 ** 32)
    random.seed(seed)

    print("=" * 80)
    print("BATCH RUNNER — Simulated Annealing & SA-Cutoff")
    print("=" * 80)
    print(f"Seed: {seed}")
    print(
        f"SA params   : T0={sa_config.T0}  Tf={sa_config.TF}  "
        f"alpha={sa_config.ALPHA}  Ns={sa_config.NS}"
    )
    print(
        f"SA-C params : T0={sa_cutoff_config.T0}  Tf={sa_cutoff_config.TF}  "
        f"alpha={sa_cutoff_config.ALPHA}  Ns={sa_cutoff_config.NS}  Na={sa_cutoff_config.NA}"
    )

    instance_files = sorted(INPUT_DIR.glob("*.json"))
    results = []
    skipped = []

    for instance_path in instance_files:
        instance_name = instance_path.stem.replace("_input", "")

        print(f"\n{'-'*60}")
        print(f"Instance: {instance_name}  ({instance_path.name})")

        try:
            instance = InstanceParser(instance_path).parse()
        except Exception as e:
            print(f"  [SKIP] Failed to parse instance: {e}")
            skipped.append(instance_name)
            continue

        solution = load_best_initial_solution(instance, instance_name)
        if solution is None:
            print(f"  [SKIP] No valid initial solution found.")
            skipped.append(instance_name)
            continue

        print(f"  Initial fitness: {solution.fitness:.2f}")

        # SA
        try:
            result = run_sa(instance, solution, instance_name, seed)
            results.append(result)
            print(f"  [SA]        Score={result['score']:.2f}  "
                  f"Improvement={result['improvement']:+.2f}  "
                  f"Time={result['time_s']:.1f}s")
        except Exception as e:
            print(f"  [SA]        ERROR: {e}")

        # SA-Cutoff (fresh deepcopy of the initial solution is handled inside the solver)
        try:
            result = run_sa_cutoff(instance, solution, instance_name, seed)
            results.append(result)
            print(f"  [SA-Cutoff] Score={result['score']:.2f}  "
                  f"Improvement={result['improvement']:+.2f}  "
                  f"Time={result['time_s']:.1f}s")
        except Exception as e:
            print(f"  [SA-Cutoff] ERROR: {e}")

    print_summary(results)

    if skipped:
        print(f"\nSkipped instances ({len(skipped)}): {', '.join(skipped)}")


if __name__ == "__main__":
    main()
