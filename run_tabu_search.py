#!/usr/bin/env python3
"""
Tabu Search runner for TV Scheduling Optimization.

Usage:
    python3 run_tabu_search.py
"""

import json
import time
import random
from pathlib import Path

from io_utils.file_selector import select_file
from io_utils.instance_parser import InstanceParser
from io_utils.initial_solution_parser import SolutionParser
from evaluators.base_evaluator import BaseEvaluator
from models.solution.solution import Solution
from utils.validator import validate_schedule_against_instance
from solvers.tabu_search_solver import TabuSearchSolver
import config.tabu_search_config as config


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


def main():
    seed = int(time.time() * 1000) % (2 ** 32)
    random.seed(seed)

    print("=" * 60)
    print("TABU SEARCH — TV Scheduling Optimization")
    print("=" * 60)
    print(f"Random Seed: {seed}")
    print(f"\nConfig:")
    print(f"  Tabu tenure:              {config.TABU_TENURE}")
    print(f"  Neighborhood size:        {config.NEIGHBORHOOD_SIZE}")
    print(f"  Max iterations:           {config.MAX_ITERATIONS}")
    print(f"  Patience:                 {config.PATIENCE}")
    print(f"  Diversification trigger:  {config.DIVERSIFICATION_TRIGGER}")
    print(f"  Intensification trigger:  {config.INTENSIFICATION_TRIGGER}")
    print(f"  Elite size:               {config.ELITE_SIZE}")

    print("\n=== Select Instance File ===")
    instance_path = select_file("data/input")
    instance = InstanceParser(instance_path).parse()
    instance_name = Path(instance_path).stem.replace("_input", "")
    print(f"Instance: {instance_path}")

    print("\n=== Loading best initial solution ===")
    candidates = []
    for folder in ["data/solutions/constructiveapproach", "data/solutions/dp_segmenting"]:
        folder_path = Path(folder)
        if not folder_path.exists():
            continue
        for f in folder_path.glob(f"{instance_name}*.json"):
            try:
                sched = SolutionParser(f).parse()
                sol = Solution(
                    evaluator=BaseEvaluator(instance),
                    selected=sched,
                    unselected_ids=[
                        p.program_id
                        for ch in instance.channels for p in ch.programs
                        if p.program_id not in {sp.program_id for sp in sched.scheduled_programs}
                    ]
                )
                candidates.append((sol.fitness, f, sched))
            except Exception:
                continue

    if not candidates:
        print(f"No initial solutions found for '{instance_name}'. Exiting.")
        return

    candidates.sort(key=lambda x: -x[0])
    best_fitness, solution_path, schedule = candidates[0]
    print(f"Found {len(candidates)} candidate(s). Using best:")
    print(f"  File:    {solution_path}")
    print(f"  Fitness: {best_fitness:.2f}")

    try:
        validate_schedule_against_instance(schedule, instance)
    except ValueError as e:
        print(f"\nValidation error:\n{e}")
        return

    evaluator = BaseEvaluator(instance)
    selected_ids = {p.program_id for p in schedule.scheduled_programs}
    unselected_ids = [
        p.program_id
        for ch in instance.channels for p in ch.programs
        if p.program_id not in selected_ids
    ]

    solution = Solution(
        evaluator=evaluator,
        selected=schedule,
        unselected_ids=unselected_ids
    )

    initial_fitness = solution.fitness
    print(f"\nInitial fitness:        {initial_fitness:.2f}")
    print(f"Scheduled programs:     {len(schedule.scheduled_programs)}")
    print(f"Unselected programs:    {len(unselected_ids)}")

    solver = TabuSearchSolver(solution=solution, instance=instance)
    best = solver.solve()

    improvement = best.fitness - initial_fitness
    print(f"\n=== FINAL RESULT ===")
    print(f"Initial fitness:   {initial_fitness:.2f}")
    print(f"Final fitness:     {best.fitness:.2f}")
    print(f"Improvement:       +{improvement:.2f}")

    # Check against existing ILS result if available
    ils_dir = Path("data/solutions/ils")
    ils_files = list(ils_dir.glob(f"{instance_name}*")) if ils_dir.exists() else []
    if ils_files:
        ils_file = max(ils_files, key=lambda x: x.stat().st_mtime)
        ils_fitness = int(ils_file.stem.split("_")[-1])
        tabu_vs_ils = best.fitness - ils_fitness
        print(f"\nVs ILS ({ils_fitness}):    {'+'if tabu_vs_ils >= 0 else ''}{tabu_vs_ils:.2f} "
              f"({'BETTER' if tabu_vs_ils > 0 else 'SAME' if tabu_vs_ils == 0 else 'WORSE'})")

    output_path = Path("data/solutions/tabu") / (
        f"{instance_name}_tabu_{int(best.fitness)}.json"
    )
    save_solution(best.selected.scheduled_programs, output_path)
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
