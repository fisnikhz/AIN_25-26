from abc import ABC, abstractmethod
from typing import List
from models.program import Program
from models.solution import Solution

class BaseSolver(ABC):
    def __init__(self, programs: List[Program]):
        self.programs = programs

    @abstractmethod
    def solve(self) -> Solution:
        pass
