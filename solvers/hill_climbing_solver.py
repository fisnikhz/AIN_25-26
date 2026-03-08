from solvers.base_solver import BaseSolver
from models.instance.instance_data import InstanceData
from models.solution.solution import Solution
from operators.swap import swap
from operators.shift import shift
from operators.shift import ShiftDirection
import config.config as config

import random


class HillClimbingSolver(BaseSolver):

    def __init__(self, solution: Solution):
        super().__init__(solution)

    def solve(self, instance: InstanceData) -> Solution:
        print("\n=== Starting Hill Climbing Optimization ===")

        for _ in range(config.MAX_ITERATIONS):
            neighbor = self.__mutate(instance)

            if neighbor.fitness >= self.solution.fitness:
                self.solution = neighbor

        return self.solution

    def __mutate(self, instance: InstanceData) -> Solution:

        coin = random.random() < 0.5
        if coin:
            copy = swap(self.solution, self.solution.evaluator.instance)
        else:
            program = random.choice(self.solution.selected)
            direction = random.choice(list(ShiftDirection))
            shamt = round(random.random() * config.MAX_SHIFT)
            # print(f"shift(instance=[jo-haver], state=[jo-haver],"
            #       f"program_id={program.program_id}, direction={direction}, shamt={shamt})")
            copy = shift(instance, self.solution, program, direction, shamt)

        return copy
