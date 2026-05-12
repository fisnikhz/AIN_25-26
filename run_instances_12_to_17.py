import subprocess
import sys
from pathlib import Path


def run_main_for_indices(start_index: int = 1, end_index: int = 17):
    project_dir = Path(__file__).resolve().parent
    main_file = project_dir / "main.py"

    python_executable = sys.executable

    for index in range(start_index, end_index + 1):
        print("\n" + "=" * 70)
        print(f"Running main.py for instance index: {index}")
        print("=" * 70)

        try:
            result = subprocess.run(
                [python_executable, str(main_file)],
                input=f"{index}\n",
                text=True,
                cwd=project_dir,
            )

            if result.returncode != 0:
                print(f"main.py failed for index {index}. Return code: {result.returncode}")
            else:
                print(f"Finished index {index}")

        except Exception as e:
            print(f"Error while running index {index}: {e}")


if __name__ == "__main__":
    run_main_for_indices(12, 17)