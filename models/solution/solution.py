import copy

from models.solution.schedule import Schedule
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
            self.selected.scheduled_programs.append(program)
            self._fitness = None

    def unselect_program(self, scheduled_program: ScheduledProgram):
        if scheduled_program in self.selected:
            self.selected.scheduled_programs.remove(scheduled_program)
            
            if scheduled_program.program_id not in self.unselected_ids:
                self.unselected_ids.append(scheduled_program.program_id)
                
            self._fitness = None

    def __deepcopy__(self, memo):
        # The evaluator holds the full read-only instance data (channels, programs).
        # Sharing it across copies avoids deep-copying megabytes of instance data
        # on every neighbor generation, which is critical for large instances.
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        result.evaluator = self.evaluator
        result.selected = copy.deepcopy(self.selected, memo)
        result.unselected_ids = copy.deepcopy(self.unselected_ids, memo)
        result._fitness = self._fitness
        return result

    def __repr__(self):
        return (f"Solution(fitness={self.fitness}, "
                f"selected={len(self.selected.scheduled_programs)}, "
                f"unselected={len(self.unselected_ids)})")
