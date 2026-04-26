#!/usr/bin/env python3
import json
from pathlib import Path

from io_utils.file_selector import select_file
from io_utils.instance_parser import InstanceParser
from evaluators.base_evaluator import BaseEvaluator
from solvers.grasp_solver import GraspSolver


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

    evaluator = BaseEvaluator(instance)

    grasp_solver = GraspSolver(evaluator)
    grasp_best = grasp_solver.solve(instance)

    print(f"\nGRASP best fitness: {grasp_best.fitness}")

    instance_name = Path(instance_path).stem.replace("_input", "")
    output_path = Path("data/solutions/grasp") / (
        f"{instance_name}_output_grasp_{int(grasp_best.fitness)}.json"
    )
    save_solution(grasp_best.selected, output_path)
    print(f"GRASP solution saved to: {output_path}")


if __name__ == "__main__":
    main()
