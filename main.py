#!/usr/bin/env python3
import json
from pathlib import Path

from io_utils.file_selector import select_file
from io_utils.instance_parser import InstanceParser
from io_utils.initial_solution_parser import SolutionParser
from evaluators.base_evaluator import BaseEvaluator
from models.solution.solution import Solution
from utils.validator import validate_schedule_against_instance

from solvers.classic_ils_solver import IteratedLocalSearchSolver


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
# MAIN
# =====================================================
def main():

    print("=== Select Instance File ===")
    instance_path = select_file("data/input")
    instance = InstanceParser(instance_path).parse()

    instance_name = Path(instance_path).stem.replace("_input", "")

    print("\n=== Loading initial solutions from 2 sources ===")
    all_candidates = get_all_initial_solutions(instance, instance_name)

    if not all_candidates:
        print(f"No initial solutions found for {instance_name} in any folder.")
        return

    print(f"Found {len(all_candidates)} solutions in total.")


    best_entry = max(
        all_candidates,
        key=lambda x: x["solution"].fitness
    )

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

    print("\n=== Running CLASSIC ILS ===")

    solver = IteratedLocalSearchSolver(best_solution)
    best_result = solver.solve(instance)

    print(f"\nFINAL ILS FITNESS: {best_result.fitness}")
    print(f"Improvement from {best_solution.fitness}: {best_result.fitness - best_solution.fitness}")

    output_path = Path("data/solutions/ils") / (
        f"{instance_name}_ils_best_initial_{int(best_result.fitness)}.json"
    )

    save_solution(best_result.selected, output_path)

    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()