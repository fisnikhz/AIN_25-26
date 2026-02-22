class Program:
    def __init__(self, program_id: int, start_time: int, end_time: int):
        self.id = program_id
        self.start_time = start_time
        self.end_time = end_time

    def duration(self) -> int:
        return self.end_time - self.start_time

    def __repr__(self):
        return f"Program(id={self.id}, start={self.start_time}, end={self.end_time})"

    def to_output_format(self):
        return [self.id, self.start_time, self.end_time]
