from solvers.base_solver import BaseSolver
from models.instance.instance_data import InstanceData
from models.solution.solution import Solution
from operators.replace import replace
from operators.shift_borders import shift_borders, TargetBorder, Mode
from operators.swap import swap
import config.config as config

import random
import copy


class IteratedLocalSearchSolver(BaseSolver):

    def __init__(self, solution: Solution):
        super().__init__(solution)

    def solve(self, instance: InstanceData) -> Solution:
        print("\n=== Starting FAST Iterated Local Search ===")

        current = self.solution
        current = self.__local_search(instance, current)
        best = current

        for i in range(config.MAX_ITERATIONS):

            if i % 5 == 0:
                print(f"[ILS] Iter {i} | Best: {best.fitness}")

            perturbed = self.__perturb(instance, current)
            candidate = self.__local_search(instance, perturbed)

            if candidate.fitness > best.fitness:
                print(f"Improved: {best.fitness} -> {candidate.fitness}")
                best = candidate

            current = candidate

        print(f"\nFinal Best Fitness: {best.fitness}")
        return best

    def __local_search(self, instance: InstanceData, solution: Solution) -> Solution:
        current = solution
        no_improve = 0

        for _ in range(getattr(config, "LOCAL_SEARCH_ITERATIONS", 20)):

            neighbor = self.__mutate(instance, current)

            if neighbor and neighbor.fitness >= current.fitness:
                current = neighbor
                no_improve = 0
            else:
                no_improve += 1

            # 🔥 early stop (speed boost)
            if no_improve >= 5:
                break

        return current

    def __perturb(self, instance: InstanceData, solution: Solution) -> Solution:
        perturbed = solution

        for _ in range(getattr(config, "PERTURBATION_STRENGTH", 2)):
            new_sol = self.__mutate(instance, perturbed)
            if new_sol:
                perturbed = new_sol

        return perturbed

    def __mutate(self, instance: InstanceData, solution: Solution) -> Solution:
        scheduled = list(solution.selected)

        if not scheduled:
            return solution

        r = random.random()

        try:

            if r < 0.45 and len(scheduled) >= 2:
                i = random.randrange(len(scheduled))
                j = i + random.choice([-1, 1]) if 0 < i < len(scheduled) - 1 else i

                if 0 <= j < len(scheduled):
                    return swap(instance, solution, scheduled[i], scheduled[j])

            elif r < 0.85:
                program = random.choice(scheduled)

                max_left = program.start
                max_right = 1440 - program.end
                if max_left <= 0 and max_right <= 0:
                    return solution

                direction = random.choice(list(TargetBorder))
                mode = random.choice(list(Mode))

                if max_left <= 0:
                    direction = TargetBorder.RIGHT
                elif max_right <= 0:
                    direction = TargetBorder.LEFT

                max_possible = max(max_left, max_right)
                shamt = random.randint(1, min(config.MAX_SHIFT, max_possible))

                return shift_borders(instance, solution, program, mode, direction, shamt)

            else:
                return replace(solution, instance)

        except Exception:
            return solution