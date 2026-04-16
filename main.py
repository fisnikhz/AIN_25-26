#!/usr/bin/env python3
import json
from pathlib import Path

from io_utils.file_selector import select_file
from io_utils.instance_parser import InstanceParser
from io_utils.initial_solution_parser import SolutionParser
from evaluators.base_evaluator import BaseEvaluator
from models.solution.solution import Solution
from utils.validator import validate_schedule_against_instance

from solvers.hill_climbing_solver import HillClimbingSolver
from solvers.classic_ils_solver import IteratedLocalSearchSolver


def save_solution(schedule, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "scheduled_programs": [
            {
                "program_id": program.program_id,
                "channel_id": program.channel_id,
                "start": program.start,
                "end": program.end,
            }
            for program in schedule
        ]
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=4)


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


def main():
    print("=== Select Instance File ===")
    instance_path = select_file("data/input")
    instance = InstanceParser(instance_path).parse()

    print("\n=== Select Solution File ===")
    solution_path = select_file("data/solutions/constructiveapproach")
    schedule = SolutionParser(solution_path).parse()

    try:
        validate_schedule_against_instance(schedule, instance)
    except ValueError as e:
        print(f"\nValidation error:\n{e}")
        return

    base_solution = build_solution(instance, schedule)
    print(f"\nInitial fitness: {base_solution.fitness}")

    print("\nChoose solver:")
    print("1 - Hill Climbing")
    print("2 - Iterated Local Search (ILS)")
    print("3 - Run BOTH (compare)")

    choice = input("Your choice: ").strip()

    instance_name = Path(instance_path).stem.replace("_input", "")

    # ---------------- HILL CLIMBING ----------------
    if choice == "1":
        solver = HillClimbingSolver(base_solution)
        best = solver.solve(instance)

        print(f"\nHill Climbing fitness: {best.fitness}")

        output_path = Path("data/solutions/hillclimbing") / (
            f"{instance_name}_output_hc_{int(best.fitness)}.json"
        )
        save_solution(best.selected, output_path)
        print(f"Saved to: {output_path}")

    # ---------------- ILS ----------------
    elif choice == "2":
        solver = IteratedLocalSearchSolver(base_solution)
        best = solver.solve(instance)

        print(f"\nILS fitness: {best.fitness}")

        output_path = Path("data/solutions/ils") / (
            f"{instance_name}_output_ils_{int(best.fitness)}.json"
        )
        save_solution(best.selected, output_path)
        print(f"Saved to: {output_path}")

    # ---------------- BOTH ----------------
    elif choice == "3":
        print("\n=== Running Hill Climbing ===")
        hc_solver = HillClimbingSolver(base_solution)
        hc_solution = hc_solver.solve(instance)

        print("\n=== Running ILS ===")
        ils_solver = IteratedLocalSearchSolver(base_solution)
        ils_solution = ils_solver.solve(instance)

        print("\n=== RESULTS ===")
        print(f"Hill Climbing: {hc_solution.fitness}")
        print(f"ILS: {ils_solution.fitness}")

        # Save both
        hc_path = Path("data/solutions/hillclimbing") / (
            f"{instance_name}_output_hc_{int(hc_solution.fitness)}.json"
        )
        ils_path = Path("data/solutions/ils") / (
            f"{instance_name}_output_ils_{int(ils_solution.fitness)}.json"
        )

        save_solution(hc_solution.selected, hc_path)
        save_solution(ils_solution.selected, ils_path)

        print(f"\nSaved HC to: {hc_path}")
        print(f"Saved ILS to: {ils_path}")

    else:
        print("Invalid choice.")


if __name__ == "__main__":
    main()