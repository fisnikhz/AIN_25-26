class ScheduledProgram:
    def __init__(self, program_id: str, channel_id: int, start :int , end: int):
        self.program_id = program_id
        self.channel_id = channel_id
        self.start = start
        self.end = end

    @property
    def duration(self) -> int:
        return self.end - self.start

    def __repr__(self) -> str:
        return (
            f"ScheduledProgram({self.program_id}, ch={self.channel_id},"
            f"{self.start}-{self.end})"
        )
