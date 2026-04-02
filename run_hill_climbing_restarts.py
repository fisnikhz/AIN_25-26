#!/usr/bin/env python3
"""
Script kryesor për Hill Climbing me Random Restarts.

Përdorim:
    python run_hill_climbing_restarts.py

Detyra:
- Hill Climbing me random restarts (parametër)
- Insertion operator çdo N iteracione ku ka vend
"""

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
from solvers.hill_climbing_restarts_solver import HillClimbingRestartsSolver
import config.config as config


def save_solution(schedule, output_path: Path):
    """Ruaj zgjidhjen në JSON."""
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
    # INICIALIZO RANDOM SEED me timestamp për randomness të vërtetë
    seed = int(time.time() * 1000) % (2**32)  # Përdor timestamp si seed
    random.seed(seed)
    
    print("="*60)
    print("HILL CLIMBING ME RANDOM RESTARTS")
    print("="*60)
    print(f"\nRandom Seed: {seed}")
    print("\nDetyra:")
    print("- Hill Climbing me random restarts (parametër)")
    print("- Insertion operator çdo N iteracione ku ka vend")
    
    # Zgjidh instance
    print("\n=== Zgjidh Instance File ===")
    instance_path = select_file("data/input")
    instance = InstanceParser(instance_path).parse()
    print(f"Instance: {instance_path}")

    # Zgjidh zgjidhjen fillestare
    print("\n=== Zgjidh Zgjidhjen Fillestare ===")
    solution_path = select_file("data/solutions/constructiveapproach")
    schedule = SolutionParser(solution_path).parse()
    print(f"Zgjidhja fillestare: {solution_path}")

    # Valido
    try:
        validate_schedule_against_instance(schedule, instance)
    except ValueError as e:
        print(f"\nGabim validimi:\n{e}")
        return

    # Krijo evaluator
    evaluator = BaseEvaluator(instance)

    # Gjej programet unselected
    unselected_ids = []
    for channel in instance.channels:
        for program in channel.programs:
            if program.program_id not in {p.program_id for p in schedule}:
                unselected_ids.append(program.program_id)

    # Krijo zgjidhjen fillestare
    solution = Solution(
        evaluator=evaluator,
        selected=schedule,
        unselected_ids=unselected_ids
    )

    print(f"\nFitness fillestare: {solution.fitness}")
    print(f"Programe të zgjedhura: {len(schedule.scheduled_programs)}")
    print(f"Programe unselected: {len(unselected_ids)}")

    # Parametrat
    print(f"\n--- Parametrat ---")
    print(f"Random Restarts: {config.NUM_RESTARTS}")
    print(f"Max Iterations: {config.MAX_ITERATIONS}")
    print(f"Insertion Interval: çdo {config.INSERTION_INTERVAL} iteracione")
    
    # Krijo dhe ekzekuto Hill Climbing solver
    solver = HillClimbingRestartsSolver(
        solution=solution,
        instance=instance,
        num_restarts=config.NUM_RESTARTS,
        insertion_interval=config.INSERTION_INTERVAL,
        max_iterations=config.MAX_ITERATIONS
    )
    
    best_solution = solver.solve()

    print(f"\n=== REZULTATI FINAL ===")
    print(f"Fitness fillestare: {solution.fitness}")
    print(f"Fitness finale: {best_solution.fitness}")
    print(f"Përmirësimi: +{best_solution.fitness - solution.fitness}")
    
    # VALIDIM FINAL: Kontrollo që programet janë brenda bounds origjinale
    print(f"\n=== VALIDIM FINAL ===")
    validation_errors = []
    program_lookup = {}
    for channel in instance.channels:
        for program in channel.programs:
            program_lookup[(channel.channel_id, program.program_id)] = program
    
    for sp in best_solution.selected.scheduled_programs:
        orig_prog = program_lookup.get((sp.channel_id, sp.program_id))
        if orig_prog:
            if sp.start < orig_prog.start or sp.end > orig_prog.end:
                validation_errors.append(
                    f"Program {sp.program_id}: scheduled [{sp.start}, {sp.end}] "
                    f"jashtë bounds origjinale [{orig_prog.start}, {orig_prog.end}]"
                )
    
    if validation_errors:
        print(f"❌ GABIME VALIDIMI ({len(validation_errors)}):")
        for error in validation_errors[:5]:
            print(f"  {error}")
        if len(validation_errors) > 5:
            print(f"  ... dhe {len(validation_errors) - 5} gabime të tjera")
        print("\n⚠️  ZGJIDHJA KA PROBLEME - por po ruhet për debugging")

    # Ruaj zgjidhjen
    instance_name = Path(instance_path).stem.replace("_input", "")
    output_path = Path("data/solutions/hillclimbing_restarts") / (
        f"{instance_name}_output_hc_restarts_{int(best_solution.fitness)}.json"
    )
    save_solution(best_solution.selected.scheduled_programs, output_path)
    print(f"\nZgjidhja u ruajt: {output_path}")


if __name__ == "__main__":
    main()
