from abc import ABC, abstractmethod
from models.solution.solution import Solution

class BaseSolver(ABC):
    def __init__(self, solution: Solution):
        self.solution = solution

    @abstractmethod
    def solve(self) -> Solution:
        pass