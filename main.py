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


def main():
    print("=== Select Instance File ===")
    instance_path = select_file("data/input")
    instance = InstanceParser(instance_path).parse()

    print("\n=== Select Solution File ===")
    solution_path = select_file("data/solutions/hillclimbing_heuristic")
    schedule = SolutionParser(solution_path).parse()

    try:
        validate_schedule_against_instance(schedule, instance)
    except ValueError as e:
        print(f"\nValidation error:\n{e}")
        return

    evaluator = BaseEvaluator(instance)

    unselected_ids = []

    for channel in instance.channels:
        for program in channel.programs:
            if program.program_id not in {p.program_id for p in schedule}:
                unselected_ids.append(program.program_id)

    # print(f"Unselected programs: {unselected_ids}")

    solution = Solution(evaluator=evaluator,
                        selected=schedule,
                        unselected_ids=unselected_ids)

    print(f"Old greedy fitness: {solution.fitness}")

    solver = HillClimbingSolver(solution)
    best_solution = solver.solve(instance)

    print(f"New hill climbing heuristic fitness: {best_solution.fitness}")

    instance_name = Path(instance_path).stem.replace("_input", "")
    output_path = Path("data/solutions/hillclimbing_heuristic") / (
        f"{instance_name}_output_hillclimbing_heuristic_{int(best_solution.fitness)}.json"
    )
    save_solution(best_solution.selected, output_path)
    print(f"Hill climbing heuristic solution saved to: {output_path}")


if __name__ == "__main__":
    main()
