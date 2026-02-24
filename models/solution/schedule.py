class Schedule:
    def __init__(self, scheduled_programs):
        self.scheduled_programs = scheduled_programs

    def __len__(self):
        return len(self.scheduled_programs)

    def __iter__(self):
        return iter(self.scheduled_programs)

    def __getitem__(self, index):
        return self.scheduled_programs[index]

    def __repr__(self):
        return f"Schedule({len(self.scheduled_programs)} programs)"
