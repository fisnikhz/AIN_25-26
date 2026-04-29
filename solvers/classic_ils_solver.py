import random
import copy
import config.classic_ils_config as config

from solvers.base_solver import BaseSolver
from models.instance.instance_data import InstanceData
from models.solution.solution import Solution

from operators.replace import replace
from operators.shift_borders import shift_borders, TargetBorder, Mode
from operators.swap import swap
from operators.insert import insert_best, insertion_stats


class IteratedLocalSearchSolver(BaseSolver):

    def __init__(self, solution: Solution):
        super().__init__(solution)
        # Cache për qasje O(1) në të dhënat e programeve të instancës
        self.program_lookup = None

    def solve(self, instance: InstanceData) -> Solution:
        print("\n=== Optimized Iterated Local Search ===")

        # Ndërtimi i lookup table një herë në fillim
        self.program_lookup = {
            (c.channel_id, p.program_id): p
            for c in instance.channels for p in c.programs
        }

        max_iter = getattr(config, "MAX_ITERATIONS", 200)
        insertion_interval = getattr(config, "INSERTION_INTERVAL", 50)

        # 1. Initial Local Search
        current = self.__local_search(instance, copy.deepcopy(self.solution))
        current = self.__repair_if_needed(current, instance)
        best = copy.deepcopy(current)

        for i in range(max_iter):
            if i % 10 == 0:
                print(f"[ILS] Iter {i} | Best fitness: {best.fitness}")

            # 2. PERTURBATION (Shaking)
            perturbed = self.__perturb(instance, current)

            # 3. LOCAL SEARCH (Hill Climbing)
            candidate = self.__local_search(instance, perturbed)
            candidate = self.__repair_if_needed(candidate, instance)

            # 4. INTENSE IMPROVEMENT
            if i > 0 and i % insertion_interval == 0:
                candidate = self.__apply_intensification(instance, candidate)

            # 5. ACCEPTANCE CRITERION
            if candidate.fitness >= current.fitness:
                current = candidate
            elif random.random() < 0.1:
                current = candidate

            # 6. UPDATE BEST
            if current.fitness > best.fitness:
                print(f"[BEST] {best.fitness} -> {current.fitness}")
                best = copy.deepcopy(current)

        print(f"\nFINAL BEST FITNESS: {best.fitness}")
        return best

    def __apply_intensification(self, instance: InstanceData, candidate: Solution) -> Solution:
        stats = insertion_stats(candidate, instance)

        print(f"\n[CHECK] Intensification Triggered:")
        print(f"  - Unselected Programs: {len(candidate.unselected_ids)}")
        print(f"  - Available Gaps: {stats.get('gaps', 0)}")
        print(f"  - Placeable (Potential): {stats.get('placeable_any', 0)}")

        # Provon Insert
        if stats.get("gaps", 0) > 0:
            print(f"[INSERT] Attempting to fill gaps...")
            inserted = insert_best(copy.deepcopy(candidate), instance)
            if inserted and self.__is_valid(inserted, instance) and inserted.fitness > candidate.fitness:
                print(f"[INSERT] Success! New fitness: {inserted.fitness}")
                return inserted
            else:
                print(f"[INSERT] No valid improvement found.")

        # Provon Replace
        print(f"[REPLACE] Starting replacement search...")
        improved = False
        current_best = candidate

        for i in range(3):
            temp = replace(copy.deepcopy(current_best), instance)
            # Sigurohemi që replacement nuk ka thyer rregullat e prioritetit
            if temp and self.__is_valid(temp, instance) and temp.fitness > current_best.fitness:
                print(f"  - [REPLACE] Iter {i}: Found improvement! ({current_best.fitness} -> {temp.fitness})")
                current_best = temp
                improved = True

        if not improved:
            print(f"  - [REPLACE] No improvement found in 3 attempts.")

        print(f"[REPLACE] Mode finished.")
        return current_best
    def __local_search(self, instance: InstanceData, solution: Solution) -> Solution:
        current = solution
        no_improve = 0
        ls_iter = getattr(config, "LOCAL_SEARCH_ITERATIONS", 20)

        for _ in range(ls_iter):
            neighbor = self.__mutate(instance, copy.deepcopy(current))
            neighbor = self.__repair_if_needed(neighbor, instance)

            if neighbor.fitness >= current.fitness:
                if neighbor.fitness > current.fitness:
                    no_improve = 0
                current = neighbor
            else:
                no_improve += 1

            if no_improve >= 10:
                break
        return current

    def __perturb(self, instance: InstanceData, solution: Solution) -> Solution:
        perturbed = copy.deepcopy(solution)
        strength = getattr(config, "PERTURBATION_STRENGTH", 3)

        for _ in range(strength):
            perturbed = self.__mutate(instance, perturbed)
            perturbed = self.__repair_if_needed(perturbed, instance)

        return perturbed

    def __mutate(self, instance: InstanceData, solution: Solution) -> Solution:
        scheduled = solution.selected.scheduled_programs
        if not scheduled: return solution

        r = random.random()
        try:
            if r < 0.5 and len(scheduled) >= 2:
                # SWAP
                p1, p2 = random.sample(scheduled, 2)
                return swap(instance, solution, p1, p2)
            else:
                # SHIFT
                program = random.choice(scheduled)
                mode = random.choice(list(Mode))
                direction = random.choice(list(TargetBorder))
                shamt = random.randint(1, getattr(config, "MAX_SHIFT", 10))

                return shift_borders(instance, solution, program, mode, direction, shamt)
        except Exception:
            return solution

    def __repair_if_needed(self, solution: Solution, instance: InstanceData) -> Solution:
        if solution is None: return None

        if self.__is_valid(solution, instance):
            return solution

        repaired = replace(copy.deepcopy(solution), instance)

        if self.__is_valid(repaired, instance):
            return repaired

        return solution

    def __is_valid(self, solution: Solution, instance: InstanceData) -> bool:
        if not solution or not solution.selected.scheduled_programs:
            return True

        for sp in solution.selected.scheduled_programs:
            # Priority Blocks (Hard Constraints)
            for block in instance.priority_blocks:
                # Overlap Control
                has_overlap = min(sp.end, block.end) > max(sp.start, block.start)

                if has_overlap:
                    # ka overlap
                    if sp.channel_id not in block.allowed_channels:
                        # print(f"Invalid: Channel {sp.channel_id} not allowed in block {block.start}-{block.end}")
                        return False
        return True
