from abc import ABC, abstractmethod
from typing import List
from models.solution.scheduled_program import ScheduledProgram
from models.solution.solution import Solution

class BaseSolver(ABC):
    def __init__(self, programs: List[ScheduledProgram]):
        self.programs = programs

    @abstractmethod
    def solve(self) -> Solution:
        pass
