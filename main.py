#!/usr/bin/env python3

from io_utils.file_selector import select_file
from io_utils.instance_parser import InstanceParser
from io_utils.initial_solution_parser import SolutionParser
from evaluators.base_evaluator import BaseEvaluator
from models.solution.solution import Solution
from utils.validator import validate_schedule_against_instance
from solvers.hill_climbing_solver import HillClimbingSolver


def main():
    print("=== Select Instance File ===")
    instance_path = select_file("data/input")
    instance = InstanceParser(instance_path).parse()
    # print(f"Loaded instance: {instance}")

    print("\n=== Select Solution File ===")
    solution_path = select_file("data/solutions/greedyscheduler")
    schedule = SolutionParser(solution_path).parse()
    # print(f"Loaded schedule: {schedule}")

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

    solution = Solution(evaluator=evaluator,
                        selected=schedule,
                        unselected_ids=unselected_ids)
    solver = HillClimbingSolver(solution)
    best_solution = solver.solve()

    print(f"Old greedy fitness: {solution.fitness}")
    print(f"New hill climbing fitness: {best_solution.fitness}")


if __name__ == "__main__":
    main()
