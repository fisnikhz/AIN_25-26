from collections.abc import Iterator
from scheduled_program import ScheduledProgram

class Schedule:
    def __init__(self, scheduled_programs: list[ScheduledProgram]):
        if scheduled_programs is not None:
            self.scheduled_programs = scheduled_programs 
        else:
            self.scheduled_programs = []

    def __len__(self) -> int:
        return len(self.scheduled_programs)

    def __iter__(self) -> Iterator[ScheduledProgram]:
        return iter(self.scheduled_programs)

    def __getitem__(self, index: int) -> ScheduledProgram:
        return self.scheduled_programs[index]

    def __repr__(self) -> str:
        return f"Schedule({len(self.scheduled_programs)} programs)"