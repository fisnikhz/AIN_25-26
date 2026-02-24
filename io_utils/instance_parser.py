import json
import sys

from models.instance.channel import Channel
from models.instance.instance_data import InstanceData
from models.instance.program import Program
from models.instance.priority_block import PriorityBlock
from models.instance.time_preference import TimePreference


class InstanceParser:
    def __init__(self, file_path):
        self.file_path = file_path

    def     parse(self):
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="ignore") as file:
                data = json.load(file)

            channels = []
            unique_program_id = 1

            for ch in data.get("channels", []):
                programs = []
                for p in ch.get("programs", []):
                    program = Program(
                        p["program_id"],
                        p["start"],
                        p["end"],
                        p["genre"],
                        p["score"],
                        unique_program_id
                    )
                    programs.append(program)
                    unique_program_id += 1

                channel_name = ch.get("channel_name", f"Channel_{ch['channel_id']}")
                channels.append(Channel(ch["channel_id"], channel_name, programs))

            priority_blocks = [
                PriorityBlock(
                    pb["start"],
                    pb["end"],
                    pb["allowed_channels"]
                ) for pb in data.get("priority_blocks", [])
            ]

            time_preferences = [
                TimePreference(
                    tp["start"],
                    tp["end"],
                    tp["preferred_genre"],
                    tp["bonus"]
                ) for tp in data.get("time_preferences", [])
            ]

            instance = InstanceData(
                opening_time=data["opening_time"],
                closing_time=data["closing_time"],
                min_duration=data["min_duration"],
                max_consecutive_genre=data["max_consecutive_genre"],
                channels_count=data["channels_count"],
                switch_penalty=data["switch_penalty"],
                termination_penalty=data["termination_penalty"],
                priority_blocks=priority_blocks,
                time_preferences=time_preferences,
                channels=channels
            )

            return instance

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
