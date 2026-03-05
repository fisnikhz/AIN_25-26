from solvers.base_solver import BaseSolver
from models.solution.solution import Solution
from operators.swap import swap
from operators.shift import shift
from operators.shift import ShiftDirection
import config.config as config

import random


class HillClimbingSolver(BaseSolver):

    def __init__(self, solution: Solution):
        super().__init__(solution)

    def solve(self) -> Solution:
        print("\n=== Starting Hill Climbing Optimization ===")

        for _ in range(config.MAX_ITERATIONS):
            neighbor = self.__mutate()

            if neighbor.fitness >= self.solution.fitness:
                self.solution = neighbor

        return self.solution

    def __mutate(self) -> Solution:

        coin = random.random() < 0.5
        if coin:
            copy = swap(self.solution, self.solution.evaluator.instance)
        else:
            program_id = random.choice(self.solution.selected).program_id
            direction = random.choice(list(ShiftDirection))
            shamt = random.random() * config.MAX_SHIFT
            copy = shift(self.solution, program_id, direction, shamt)

        return copy
