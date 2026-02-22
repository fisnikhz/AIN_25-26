from typing import List, Optional
from models.program import Program

class Solution:
    def __init__(self, selected: Optional[List[Program]] = None, unselected_ids: Optional[List[int]] = None):
        self.selected = selected if selected is not None else []
        self.unselected_ids = unselected_ids if unselected_ids is not None else []
        self._fitness: Optional[float] = None

    @property
    def fitness(self) -> float:
        if self._fitness is None:
            self._fitness = self.calculate_fitness()
        return self._fitness

    def calculate_fitness(self) -> float:
        return float(len(self.selected))

    def select_program(self, program: Program):
        if program.id in self.unselected_ids:
            self.unselected_ids.remove(program.id)
        
        if program not in self.selected:
            self.selected.append(program)
            self._fitness = None

    def unselect_program(self, program: Program):
        if program in self.selected:
            self.selected.remove(program)
            self._fitness = None
        
        if program.id not in self.unselected_ids:
            self.unselected_ids.append(program.id)

    def __repr__(self):
        return (f"Solution(fitness={self.fitness}, "
                f"selected={len(self.selected)}, "
                f"unselected={len(self.unselected_ids)})")
