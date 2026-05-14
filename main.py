#!/usr/bin/env python3
import json
import random
import time
from pathlib import Path

from io_utils.file_selector import select_file
from io_utils.instance_parser import InstanceParser
from io_utils.initial_solution_parser import SolutionParser
from evaluators.base_evaluator import BaseEvaluator
from models.solution.solution import Solution
from utils.validator import validate_schedule_against_instance

from solvers.classic_ils_solver import IteratedLocalSearchSolver
from solvers.simulated_annealing_solver import SimulatedAnnealingSolver
from solvers.simulated_annealing_cutoff_solver import SimulatedAnnealingCutoffSolver

import config.simulated_annealing_config as sa_config
import config.simulated_annealing_cutoff_config as sa_cutoff_config


# =====================================================
# SOLVERS MENU
# =====================================================
SOLVERS = {
    "1": "Classic ILS",
    "2": "Simulated Annealing (SA)",
    "3": "Simulated Annealing with Cutoff (SA-Cutoff)",
}


def select_solver() -> str:
    print("\n=== Select Solver ===")
    for key, name in SOLVERS.items():
        print(f"  {key}. {name}")
    while True:
        choice = input("Enter choice [1-3]: ").strip()
        if choice in SOLVERS:
            return choice
        print("Invalid choice. Please enter 1, 2, or 3.")


# =====================================================
# HELPERS
# =====================================================

def save_solution(schedule, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "scheduled_programs": [
            {
                "program_id": p.program_id,
                "channel_id": p.channel_id,
                "start": p.start,
                "end": p.end,
            }
            for p in schedule
        ]
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)


def build_solution(instance, schedule):
    evaluator = BaseEvaluator(instance)

    selected_ids = {p.program_id for p in schedule}
    unselected_ids = []

    for channel in instance.channels:
        for program in channel.programs:
            if program.program_id not in selected_ids:
                unselected_ids.append(program.program_id)

    return Solution(
        evaluator=evaluator,
        selected=schedule,
        unselected_ids=unselected_ids
    )


def get_all_initial_solutions(instance, instance_name: str):

    directories = [
        Path("data/solutions/constructiveapproach"),
        Path("data/solutions/dp_segmenting")
    ]

    solutions = []

    for directory in directories:
        if not directory.exists():
            continue

        for file_path in directory.glob(f"{instance_name}*.json"):
            try:
                schedule = SolutionParser(file_path).parse()
                sol = build_solution(instance, schedule)
                solutions.append({
                    "schedule": schedule,
                    "solution": sol,
                    "path": file_path,
                    "folder": directory.name
                })
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

    return solutions


# =====================================================
# SOLVER RUNNERS
# =====================================================

def _print_final_score(solver_name: str, instance_name: str, initial_fitness: float, best_fitness: float, output_path: Path):
    print(f"\n{'='*60}")
    print(f"  FINAL SCORE — {solver_name}")
    print(f"{'='*60}")
    print(f"  Instance   : {instance_name}")
    print(f"  Initial    : {initial_fitness:.2f}")
    print(f"  Best Score : {best_fitness:.2f}")
    print(f"  Improvement: +{best_fitness - initial_fitness:.2f}")
    print(f"  Saved to   : {output_path}")
    print(f"{'='*60}")


def run_ils(instance, solution, instance_name: str):
    print("\n=== Running CLASSIC ILS ===")

    solver = IteratedLocalSearchSolver(solution)
    best = solver.solve(instance)

    output_path = Path("data/solutions/ils") / (
        f"{instance_name}_ils_best_initial_{int(best.fitness)}.json"
    )
    save_solution(best.selected, output_path)
    _print_final_score("Classic ILS", instance_name, solution.fitness, best.fitness, output_path)


def run_sa(instance, solution, instance_name: str, seed: int):
    print(f"\n=== Running SIMULATED ANNEALING ===")
    print(f"T0={sa_config.T0}  Tf={sa_config.TF}  alpha={sa_config.ALPHA}  Ns={sa_config.NS}")

    solver = SimulatedAnnealingSolver(
        solution=solution,
        t0=sa_config.T0,
        tf=sa_config.TF,
        alpha=sa_config.ALPHA,
        ns=sa_config.NS,
        max_shift=sa_config.MAX_SHIFT,
        seed=seed,
    )
    best = solver.solve(instance)

    output_path = Path("data/solutions/simulated_annealing") / instance_name / (
        f"{instance_name}_sa_{int(best.fitness)}.json"
    )
    save_solution(best.selected.scheduled_programs, output_path)
    _print_final_score("Simulated Annealing", instance_name, solution.fitness, best.fitness, output_path)


def run_sa_cutoff(instance, solution, instance_name: str, seed: int):
    print(f"\n=== Running SIMULATED ANNEALING WITH CUTOFF ===")
    print(
        f"T0={sa_cutoff_config.T0}  Tf={sa_cutoff_config.TF}  "
        f"alpha={sa_cutoff_config.ALPHA}  Ns={sa_cutoff_config.NS}  Na={sa_cutoff_config.NA}"
    )

    solver = SimulatedAnnealingCutoffSolver(
        solution=solution,
        t0=sa_cutoff_config.T0,
        tf=sa_cutoff_config.TF,
        alpha=sa_cutoff_config.ALPHA,
        ns=sa_cutoff_config.NS,
        na=sa_cutoff_config.NA,
        max_shift=sa_cutoff_config.MAX_SHIFT,
        seed=seed,
    )
    best = solver.solve(instance)

    output_path = Path("data/solutions/simulated_annealing_cutoff") / instance_name / (
        f"{instance_name}_sa_cutoff_{int(best.fitness)}.json"
    )
    save_solution(best.selected.scheduled_programs, output_path)
    _print_final_score("Simulated Annealing with Cutoff", instance_name, solution.fitness, best.fitness, output_path)


# =====================================================
# MAIN
# =====================================================
def main():
    seed = int(time.time() * 1000) % (2 ** 32)
    random.seed(seed)

    print("=== Select Instance File ===")
    instance_path = select_file("data/input")
    instance = InstanceParser(instance_path).parse()

    instance_name = Path(instance_path).stem.replace("_input", "")

    solver_choice = select_solver()

    print("\n=== Loading initial solutions from 2 sources ===")
    all_candidates = get_all_initial_solutions(instance, instance_name)

    if not all_candidates:
        print(f"No initial solutions found for {instance_name} in any folder.")
        return

    print(f"Found {len(all_candidates)} solutions in total.")

    best_entry = max(all_candidates, key=lambda x: x["solution"].fitness)

    best_schedule = best_entry["schedule"]
    best_solution = best_entry["solution"]
    best_path = best_entry["path"]
    source_folder = best_entry["folder"]

    print("\n=== BEST INITIAL SELECTED ===")
    print(f"Source Folder: {source_folder}")
    print(f"File: {best_path.name}")
    print(f"Initial fitness (Best): {best_solution.fitness}")

    try:
        validate_schedule_against_instance(best_schedule, instance)
    except ValueError as e:
        print(f"Validation error:\n{e}")
        return

    if solver_choice == "1":
        run_ils(instance, best_solution, instance_name)
    elif solver_choice == "2":
        run_sa(instance, best_solution, instance_name, seed)
    elif solver_choice == "3":
        run_sa_cutoff(instance, best_solution, instance_name, seed)


if __name__ == "__main__":
    main()
