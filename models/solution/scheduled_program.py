class ScheduledProgram:
    def __init__(self, program_id, channel_id, start, end):
        self.program_id = program_id
        self.channel_id = channel_id
        self.start = start
        self.end = end

    @property
    def duration(self):
        return self.end - self.start

    def __repr__(self):
        return f"ScheduledProgram({self.program_id}, ch={self.channel_id}, {self.start}-{self.end})"
