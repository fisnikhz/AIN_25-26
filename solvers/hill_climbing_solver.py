from solvers.base_solver import BaseSolver
from models.instance.instance_data import InstanceData
from models.solution.solution import Solution
from operators.replace import replace
from operators.shift import shift
from operators.shift import ShiftDirection
import config.config as config

import random


class HillClimbingSolver(BaseSolver):

    def __init__(self, solution: Solution):
        super().__init__(solution)

    def solve(self, instance: InstanceData) -> Solution:
        print("\n=== Starting Hill Climbing Optimization ===")

        initial_fitness = self.solution.fitness

        for i in range(config.MAX_ITERATIONS):
            neighbor = self.__mutate(instance)

            # --- VERIFICATION PART ---
            if neighbor.fitness > self.solution.fitness:
                print(f"Iteration {i}: Fitness improved! {self.solution.fitness} -> {neighbor.fitness}")
                self.solution = neighbor
            elif neighbor.fitness == self.solution.fitness:
                # Still accept equal moves to explore the "plateau"
                self.solution = neighbor

        print(f"Total Improvement: {initial_fitness} -> {self.solution.fitness}")
        return self.solution

    def __mutate(self, instance: InstanceData) -> Solution:

        coin = random.random() < 0.5
        # coin = True
        if coin:
            copy = replace(self.solution, instance) 
            # print(f'fitness origjinal vs ai i kopjës: {self.solution.fitness} vs {copy.fitness}')
        else:
            program = random.choice(self.solution.selected)
            direction = random.choice(list(ShiftDirection))
            shamt = round(random.random() * config.MAX_SHIFT)
            # print(f"shift(instance=[jo-haver], state=[jo-haver],"
            #       f"program_id={program.program_id}, direction={direction}, shamt={shamt})")
            copy = shift(instance, self.solution, program, direction, shamt)

        return copy
