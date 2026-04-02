from solvers.base_solver import BaseSolver
from models.instance.instance_data import InstanceData
from models.solution.solution import Solution
from operators.replace import replace, replace_heuristic
from operators.shift_borders import shift_borders, shift_borders_heuristic, TargetBorder, Mode
from operators.swap import swap, swap_heuristic
import config.config as config

import random
from copy import deepcopy


class HillClimbingSolver(BaseSolver):

    def __init__(self, solution: Solution):
        super().__init__(solution)

    def solve(self, instance: InstanceData) -> Solution:
        print("\n=== Starting Hill Climbing Optimization ===")

        initial_solution = deepcopy(self.solution)
        best_solution = deepcopy(self.solution)
        initial_fitness = self.solution.fitness

        for restart in range(config.RESTARTS):
            self.solution = deepcopy(initial_solution)
            stagnant_iterations = 0

            for i in range(config.MAX_ITERATIONS):
                neighbor = self.__mutate(instance)

                if neighbor.fitness > self.solution.fitness:
                    print(
                        f"Restart {restart + 1}, iteration {i}: "
                        f"Fitness improved! {self.solution.fitness} -> {neighbor.fitness}"
                    )
                    self.solution = neighbor
                    stagnant_iterations = 0
                elif neighbor.fitness == self.solution.fitness:
                    # Still accept equal moves to explore the plateau.
                    self.solution = neighbor
                    stagnant_iterations += 1
                else:
                    stagnant_iterations += 1

                if stagnant_iterations >= config.MAX_STAGNANT_ITERATIONS:
                    break

            if self.solution.fitness > best_solution.fitness:
                best_solution = deepcopy(self.solution)

        self.solution = best_solution
        print(
            f"Best improvement after {config.RESTARTS} restarts: "
            f"{initial_fitness} -> {self.solution.fitness}"
        )
        return self.solution

    def __mutate(self, instance: InstanceData) -> Solution:
        if random.random() < 0.8:
            neighbor = self.__heuristic_mutate(instance)
            if neighbor is not self.solution:
                return neighbor
        scheduled = list(self.solution.selected)
        return self.__random_mutate(instance, scheduled)

    def __heuristic_mutate(self, instance: InstanceData) -> Solution:
        current_fitness = self.solution.fitness
        best_neighbor = self.solution
        operations = [
            lambda solution, inst: shift_borders_heuristic(inst, solution),
            lambda solution, inst: replace_heuristic(solution, inst),
        ]
        if random.random() < 0.2:
            operations.append(lambda solution, inst: swap_heuristic(inst, solution))

        for operation in operations:
            neighbor = operation(self.solution, instance)
            if neighbor.fitness > best_neighbor.fitness:
                best_neighbor = neighbor
            elif (
                neighbor.fitness == current_fitness
                and best_neighbor is self.solution
                and neighbor is not self.solution
            ):
                best_neighbor = neighbor

        return best_neighbor

    def __random_mutate(self, instance: InstanceData, scheduled=None) -> Solution:
        scheduled = list(self.solution.selected) if scheduled is None else scheduled
        mutation_ops = []

        if len(scheduled) >= 2:
            def swap_op():
                i = random.randrange(len(scheduled))
                possible_j = []
                if i > 0:
                    possible_j.append(i - 1)
                if i < len(scheduled) - 1:
                    possible_j.append(i + 1)
                if possible_j:
                    j = random.choice(possible_j)
                    program_a = scheduled[i]
                    program_b = scheduled[j]
                    return swap(instance, self.solution, program_a, program_b)
                return self.solution
            mutation_ops.append(swap_op)

        mutation_ops.append(lambda: self.__random_shift(instance, scheduled))

        def replace_op():
            return replace(self.solution, instance)
        mutation_ops.append(replace_op)

        op = random.choice(mutation_ops)
        return op()

    def __random_shift(self, instance: InstanceData, scheduled) -> Solution:
        if not scheduled:
            return self.solution

        program = random.choice(scheduled)
        direction = random.choice(list(TargetBorder))
        mode = random.choice(list(Mode))
        shamt = round(random.random() * config.MAX_SHIFT)
        return shift_borders(instance, self.solution, program, mode, direction, shamt)
