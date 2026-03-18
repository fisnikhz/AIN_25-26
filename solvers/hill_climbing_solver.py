from solvers.base_solver import BaseSolver
from models.instance.instance_data import InstanceData
from models.solution.solution import Solution
from operators.replace import replace
from operators.shift_borders import shift_borders, TargetBorder, Mode
from operators.swap import swap
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
        scheduled = list(self.solution.selected)
        mutation_ops = []

        if len(scheduled) >= 2:
            def swap_op():
                print("Operator chosen: swap")
                i = random.randrange(len(scheduled))
                offsets = [(1, -1), (1, 1), (2, -1), (2, 1)]
                random.shuffle(offsets)
                for offset, direction in offsets:
                    j = i + direction * offset
                    if j < 0 or j >= len(scheduled) or j == i:
                        continue
                    program_a = scheduled[i]
                    program_b = scheduled[j]
                    return swap(instance, self.solution, program_a, program_b)
                return self.solution
            mutation_ops.append(swap_op)

        def shift_op():
            print("Operator chosen: shift_borders")
            program = random.choice(scheduled)
            direction = random.choice(list(TargetBorder))
            mode = random.choice(list(Mode))
            shamt = round(random.random() * config.MAX_SHIFT)
            return shift_borders(instance, self.solution, program, mode, direction, shamt)
        mutation_ops.append(shift_op)

        def replace_op():
            print("Operator chosen: replace")
            return replace(self.solution, instance)
        mutation_ops.append(replace_op)

        op = random.choice(mutation_ops)
        return op()