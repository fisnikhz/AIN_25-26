class Schedule:
    """
    The class that represents a selection (a chosen program in a channel).
    """

    def __init__(
        self,
        program_id,
        start,
        end,
        fitness,
        channel_id=None,
        channel=None,
        unique_program_id=None
    ):
        resolved_channel = channel_id if channel_id is not None else channel
        if resolved_channel is None:
            raise ValueError("Schedule requires channel_id or channel")

        self.program_id = program_id
        self.channel_id = resolved_channel
        self.channel = resolved_channel
        self.start = start
        self.end = end
        self.fitness = fitness
        self.unique_program_id = unique_program_id if unique_program_id is not None else program_id

    def to_dict(self):
        """
        Converts the Schedule object into a serializable dictionary.
        """
        return {
            "program_id": self.program_id,
            "channel_id": self.channel_id,
            "start": self.start,
            "end": self.end,
            "fitness": self.fitness,
            "unique_program_id": self.unique_program_id
        }

    def __repr__(self):
        return (f"Schedule(program_id={self.program_id}, channel_id={self.channel_id},"
                f"start={self.start}, end={self.end}, "
                f"fitness={self.fitness}, unique_program_id={self.unique_program_id})")
