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
        r = random.random()

        if 0 <= r < 0.33:
            program = random.choice(self.solution.selected)
            direction = random.choice(list(TargetBorder))
            mode = random.choice(list(Mode))
            shamt = round(random.random() * config.MAX_SHIFT)
            return shift_borders(instance, self.solution, program, mode, direction, shamt)
        elif 0.33 <= r < 0.66:
            return replace(self.solution, instance)
        else:
            scheduled = list(self.solution.selected)
            if len(scheduled) < 2:
                return replace(self.solution, instance)

            i = random.randrange(len(scheduled))
            offsets = [(1, -1), (1, 1), (2, -1), (2, 1)]
            random.shuffle(offsets)

            best = None
            tried = 0
            for offset, direction in offsets:
                if tried >= 2:
                    break
                j = i + direction * offset
                if j < 0 or j >= len(scheduled) or j == i:
                    continue

                program_a = scheduled[i]
                program_b = scheduled[j]
                mode = 2 if random.random() < 0.5 else 1
                candidate = swap(instance, self.solution, program_a, program_b, mode=mode)

                tried += 1
                if candidate is self.solution:
                    continue
                if best is None or candidate.fitness > best.fitness:
                    best = candidate

            return best if best is not None else replace(self.solution, instance)
