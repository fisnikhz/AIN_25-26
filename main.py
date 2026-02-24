from io_utils.file_selector import select_file
from io_utils.instance_parser import InstanceParser
from io_utils.initial_solution_parser import SolutionParser
from evaluators.base_evaluator import BaseEvaluator
from models.solution.solution import Solution
from utils.validator import validate_schedule_against_instance


def main():
    print("=== Select Instance File ===")
    instance_path = select_file("data/input")
    instance = InstanceParser(instance_path).parse()
    print(f"Loaded instance: {instance}")

    print("\n=== Select Solution File ===")
    solution_path = select_file("data/solutions")
    schedule = SolutionParser(solution_path).parse()
    print(f"Loaded schedule: {schedule}")

    try:
        validate_schedule_against_instance(schedule, instance)
    except ValueError as e:
        print(f"\nValidation error:\n{e}")
        return

    evaluator = BaseEvaluator(instance)
    solution = Solution(evaluator, selected=schedule.scheduled_programs)
    print(f"\nTotal score: {solution.fitness}")


if __name__ == "__main__":
    main()
