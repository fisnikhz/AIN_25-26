from schedule import Schedule
from models.solution.scheduled_program import ScheduledProgram
from evaluators.evaluator import Evaluator


class Solution:
    def __init__(self, evaluator: Evaluator,
                 selected: Schedule = None,
                 unselected_ids: list[int] = None):
        self.evaluator = evaluator
        self.selected = selected
        self.unselected_ids = unselected_ids if unselected_ids is not None else []
        self._fitness: float = None

    @property
    def fitness(self) -> float:
        if self._fitness is None:
            self._fitness = self.calculate_fitness()
        return self._fitness

    def calculate_fitness(self) -> float:
        return float(self.evaluator.evaluate(self.selected))

    def select_program(self, program: ScheduledProgram):
        if program.program_id in self.unselected_ids:
            self.unselected_ids.remove(program.program_id)

        if program not in self.selected:
            self.selected.append(program)
            self._fitness = None

    def unselect_program(self, program: ScheduledProgram):
        if program in self.selected:
            self.selected.remove(program)
            self._fitness = None

        if program.program_id not in self.unselected_ids:
            self.unselected_ids.append(program.program_id)

    def __repr__(self):
        return (f"Solution(fitness={self.fitness}, "
                f"selected={len(self.selected)}, "
                f"unselected={len(self.unselected_ids)})")
