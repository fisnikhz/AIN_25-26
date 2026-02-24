import json
import sys

from models.solution.scheduled_program import ScheduledProgram
from models.solution.schedule import Schedule


class SolutionParser:
    def __init__(self, file_path):
        self.file_path = file_path

    def parse(self):
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="ignore") as file:
                data = json.load(file)

            scheduled_programs = [
                ScheduledProgram(
                    program_id=sp["program_id"],
                    channel_id=sp["channel_id"],
                    start=sp["start"],
                    end=sp["end"]
                )
                for sp in data.get("scheduled_programs", [])
            ]

            return Schedule(scheduled_programs)

        except FileNotFoundError:
            print(f"File not found: {self.file_path}")
            sys.exit(1)
        except PermissionError:
            print(f"Permission denied when accessing: {self.file_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")
            sys.exit(1)
        except KeyError as e:
            print(f"Missing required field in JSON: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}")
            sys.exit(1)
