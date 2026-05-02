import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from io_utils.file_selector import select_file
from scheduling_intelligent_ils.common import load_instance, save_solution
from scheduling_intelligent_ils.intelligent_ils_scheduler import AdaptiveHybridILSScheduler

def main():
    print("========================================")
    print("        INTELLIGENT ILS SCHEDULER       ")
    print("========================================")
    
    print("\n=== Select Instance File ===")
    instance_path_str = select_file("data/input")
    
    if not instance_path_str:
        print("No file selected. Exiting program...")
        return
        
    instance_path = Path(instance_path_str)
    instance = load_instance(instance_path)

    print(f"\nRunning algorithm for instance: {instance_path.name}...")
    solver = AdaptiveHybridILSScheduler(instance, verbose=True)
    solution = solver.generate_solution()

    print(f"\nFinal Result (Fitness Score): {solution.total_score}")

    instance_name = instance_path.stem.replace("_input", "")
    output_dir = PROJECT_ROOT / "data" / "solutions" / "intelligent_ils"
    output_path = output_dir / f"{instance_name}_output_intelligentils_{int(solution.total_score)}.json"
    
    save_solution(solution, output_path)
    
    print(f"Solution successfully saved to: {output_path}")

if __name__ == "__main__":
    main()