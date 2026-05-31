#!/usr/bin/env python3
"""
Batch Tabu Search runner for all 18 instances.
Non-interactive: auto-selects best initial solution and runs solver on all instances.
Outputs results to data/solutions/tabu_batch_results.json
"""

import json
import time
import random
from pathlib import Path
from datetime import datetime

from io_utils.instance_parser import InstanceParser
from io_utils.initial_solution_parser import SolutionParser
from evaluators.base_evaluator import BaseEvaluator
from models.solution.solution import Solution
from utils.validator import validate_schedule_against_instance
from solvers.tabu_search_solver import TabuSearchSolver
import config.tabu_search_config as config


def find_best_initial_solution(instance_name: str, instance: object) -> tuple:
    """Auto-select best initial solution matching instance_name.
    Tries both the full name and the name with '_input' suffix removed
    to handle Beam Search team's different naming convention."""
    candidates = []
    search_patterns = {instance_name}
    if instance_name.endswith('_input'):
        search_patterns.add(instance_name[:-len('_input')])

    for folder in ["data/solutions/constructiveapproach", "data/solutions/dp_segmenting"]:
        folder_path = Path(folder)
        if not folder_path.exists():
            continue
        for pattern in search_patterns:
            for f in folder_path.glob(f"{pattern}*.json"):
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
        return None, None, None

    candidates.sort(key=lambda x: -x[0])
    return candidates[0]


def run_tabu_on_instance(instance_name: str, instance_path: str) -> dict:
    """Run Tabu Search on a single instance. Returns result dict."""
    result = {
        "instance": instance_name,
        "status": "ERROR",
        "initial_fitness": None,
        "final_fitness": None,
        "improvement": None,
        "iterations": None,
        "error": None,
    }

    try:
        # Parse instance
        instance = InstanceParser(instance_path).parse()

        # Find best initial solution
        best_fitness, solution_path, schedule = find_best_initial_solution(instance_name, instance)

        if schedule is None:
            result["error"] = f"No initial solution found for {instance_name}"
            return result

        # Validate
        validate_schedule_against_instance(schedule, instance)

        # Create Solution
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

        # Run solver (suppress normal output)
        solver = TabuSearchSolver(solution=solution, instance=instance)

        # Temporarily redirect stdout to suppress verbose output
        import sys
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            best = solver.solve()
        finally:
            sys.stdout = old_stdout

        final_fitness = best.fitness
        improvement = final_fitness - initial_fitness

        # Save result
        output_path = Path("data/solutions/tabu") / (
            f"{instance_name}_tabu_{int(final_fitness)}.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "scheduled_programs": [
                {
                    "program_id": p.program_id,
                    "channel_id": p.channel_id,
                    "start": p.start,
                    "end": p.end,
                }
                for p in best.selected.scheduled_programs
            ]
        }
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)

        result["status"] = "OK"
        result["initial_fitness"] = initial_fitness
        result["final_fitness"] = final_fitness
        result["improvement"] = improvement
        result["iterations"] = solver.stats['iterations']

        return result

    except Exception as e:
        result["error"] = str(e)
        return result


def main():
    start_time = time.time()

    # List of all 18 instances
    instances = [
        "australia_iptv",
        "canada_pw",
        "china_pw",
        "croatia_tv_input",
        "france_iptv",
        "germany_tv_input",
        "kosovo_tv_input",
        "netherlands_tv_input",
        "singapore_pw",
        "spain_iptv",
        "toy",
        "toy1",
        "uk_iptv",
        "uk_tv_input",
        "us_iptv",
        "usa_tv_input",
        "youtube_gold",
        "youtube_premium",
    ]

    print("=" * 70)
    print("BATCH TABU SEARCH — Running all 18 instances")
    print("=" * 70)
    print(f"Start time: {datetime.now().isoformat()}")
    print(f"Config: TABU_TENURE={config.TABU_TENURE}, NEIGHBORHOOD_SIZE={config.NEIGHBORHOOD_SIZE}, MAX_ITERATIONS={config.MAX_ITERATIONS}")
    print()

    results = []

    for i, instance_name in enumerate(instances, 1):
        instance_path = f"data/input/{instance_name}.json"

        # Check file exists
        if not Path(instance_path).exists():
            print(f"[{i:2d}/18] {instance_name:30s} SKIPPED (not found)")
            continue

        print(f"[{i:2d}/18] {instance_name:30s} ... ", end="", flush=True)
        iter_start = time.time()

        result = run_tabu_on_instance(instance_name, instance_path)
        results.append(result)

        iter_time = time.time() - iter_start

        if result["status"] == "OK":
            improvement_str = f"+{result['improvement']:.0f}" if result['improvement'] > 0 else f"{result['improvement']:.0f}"
            print(f"OK ({result['final_fitness']:.0f}, {improvement_str}, {result['iterations']} iters, {iter_time:.1f}s)")
        else:
            print(f"ERROR: {result['error']}")

    # Save results to JSON
    output_json = Path("data/solutions/tabu_batch_results.json")
    output_json.parent.mkdir(parents=True, exist_ok=True)

    with output_json.open("w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_time_seconds": time.time() - start_time,
            "config": {
                "TABU_TENURE": config.TABU_TENURE,
                "NEIGHBORHOOD_SIZE": config.NEIGHBORHOOD_SIZE,
                "MAX_ITERATIONS": config.MAX_ITERATIONS,
                "PATIENCE": config.PATIENCE,
                "DIVERSIFICATION_TRIGGER": config.DIVERSIFICATION_TRIGGER,
                "INTENSIFICATION_TRIGGER": config.INTENSIFICATION_TRIGGER,
            },
            "results": results,
        }, f, indent=2)

    # Print summary
    print()
    print("=" * 70)
    print("BATCH RESULTS SUMMARY")
    print("=" * 70)

    ok_results = [r for r in results if r["status"] == "OK"]
    total_improvement = sum(r["improvement"] for r in ok_results)
    avg_improvement = total_improvement / len(ok_results) if ok_results else 0

    print(f"Completed: {len(ok_results)}/{len(results)}")
    print(f"Total improvement: +{total_improvement:.0f}")
    print(f"Average improvement per instance: +{avg_improvement:.2f}")
    print(f"Total time: {time.time() - start_time:.1f}s")
    print()
    print(f"Results saved to: {output_json}")


if __name__ == "__main__":
    main()
