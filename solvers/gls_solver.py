# solvers/gls_solver.py

import random
from copy import deepcopy
from collections import defaultdict

import config.gls_config as config

from solvers.base_solver import BaseSolver
from models.instance.instance_data import InstanceData
from models.solution.scheduled_program import ScheduledProgram
from models.solution.solution import Solution

from operators.swap import swap
from operators.shift_borders import shift_borders, TargetBorder, Mode
from operators.replace import replace
from operators.insert import insert_best
from operators.remove import remove


class GuidedLocalSearchSolver(BaseSolver):
    def __init__(self, solution: Solution):
        super().__init__(solution)

        self.penalties = defaultdict(int)
        self.program_lookup = {}

        self.beta = getattr(config, "GLS_BETA", None)
        self.max_iterations = getattr(config, "GLS_MAX_ITERATIONS", 500)
        self.local_search_steps = getattr(config, "GLS_LOCAL_SEARCH_STEPS", 40)
        self.candidates_per_step = getattr(config, "GLS_CANDIDATES_PER_STEP", 12)
        self.max_shift = getattr(config, "MAX_SHIFT", 10)

        self.alpha = getattr(config, "GLS_ALPHA", 0.12)
        self.acceptance_drop_ratio = getattr(config, "GLS_ACCEPTANCE_DROP_RATIO", 0.02)
        self.intensification_interval = getattr(config, "GLS_INTENSIFICATION_INTERVAL", 10)
        self.restart_after = getattr(config, "GLS_RESTART_AFTER", 80)

    def solve(self, instance: InstanceData) -> Solution:
        print("\n=== Guided Local Search ===")

        self.program_lookup = {
            (channel.channel_id, program.program_id): program
            for channel in instance.channels
            for program in channel.programs
        }

        current = deepcopy(self.solution)
        best = deepcopy(current)

        if self.beta is None:
            self.beta = self.__estimate_beta(current)

        print(f"[GLS] beta = {self.beta}")

        no_improve = 0

        for iteration in range(self.max_iterations):
            local_steps = random.randint(5, self.local_search_steps)

            for _ in range(local_steps):
                neighbor = self.__best_neighbor_from_pool(instance, current, best)

                if neighbor is None:
                    continue

                if neighbor.fitness > best.fitness:
                    print(f"[BEST] {best.fitness} -> {neighbor.fitness}")
                    best = deepcopy(neighbor)
                    current = deepcopy(neighbor)
                    no_improve = 0
                    continue

                if self.__should_accept(current, neighbor, best):
                    current = neighbor
                else:
                    no_improve += 1

            # Penalizo features që po e mbajnë current në local optimum
            self.__update_penalties(current)

            # Intensification: provo me e mbushë / përmirësu current
            if iteration > 0 and iteration % self.intensification_interval == 0:
                intensified = self.__intensify(instance, current)

                if intensified.fitness >= current.fitness:
                    current = intensified

                if current.fitness > best.fitness:
                    print(f"[BEST] {best.fitness} -> {current.fitness}")
                    best = deepcopy(current)
                    no_improve = 0

            # Restart i kontrolluar nëse nuk ka përmirësim gjatë
            if no_improve >= self.restart_after:
                current = self.__restart_from_best(instance, best)
                self.beta *= 0.90
                no_improve = 0
                print(f"[GLS] restart from best | beta = {self.beta:.4f}")

            if iteration % 1 == 0:
                print(
                    f"[GLS] Iter {iteration} | "
                    f"Current: {current.fitness} | "
                    f"Best: {best.fitness} | "
                    f"Adjusted: {self.__adjusted_quality(current):.2f} | "
                    f"PenaltySum: {sum(self.penalties.values())}"
                )

        print(f"\nFINAL GLS FITNESS: {best.fitness}")
        return best

    def __best_neighbor_from_pool(
        self,
        instance: InstanceData,
        solution: Solution,
        best: Solution,
    ) -> Solution | None:
        """
        Instead of accepting one random move, generate several candidate moves
        and select the best one according to adjusted quality.
        """
        best_neighbor = None
        best_score = float("-inf")

        for _ in range(self.candidates_per_step):
            candidate = self.__tweak(instance, solution)

            if candidate is None:
                continue

            adjusted = self.__adjusted_quality(candidate)

            # Small bonus if candidate improves normal fitness.
            # This prevents GLS from over-following penalties only.
            if candidate.fitness > solution.fitness:
                adjusted += 0.25 * (candidate.fitness - solution.fitness)

            # Strong bonus if candidate improves global best.
            if candidate.fitness > best.fitness:
                adjusted += 0.50 * (candidate.fitness - best.fitness)

            if adjusted > best_score:
                best_score = adjusted
                best_neighbor = candidate

        return best_neighbor

    def __tweak(self, instance: InstanceData, solution: Solution) -> Solution:
        scheduled = solution.selected.scheduled_programs

        if not scheduled:
            return solution

        r = random.random()

        try:
            if r < 0.25 and len(scheduled) >= 2:
                p1, p2 = random.sample(scheduled, 2)
                return swap(instance, solution, p1, p2)

            elif r < 0.50:
                program = random.choice(scheduled)
                mode = random.choice(list(Mode))
                border = random.choice(list(TargetBorder))
                shamt = random.randint(1, self.max_shift)

                return shift_borders(instance, solution, program, mode, border, shamt)

            elif r < 0.68:
                return replace(deepcopy(solution), instance)

            elif r < 0.84:
                return insert_best(deepcopy(solution), instance)

            else:
                # GLS zgjedh cilin program me largu.
                program_to_remove = self.__select_program_for_removal(solution, instance)

                if program_to_remove is None:
                    return solution

                removed = remove(solution, program_to_remove)

                # Remove vetëm e prish schedule-in.
                # Për performancë më të mirë, menjëherë provojmë me e rindërtu me insert_best.
                repaired = insert_best(deepcopy(removed), instance)

                if repaired.fitness >= removed.fitness:
                    return repaired

                return removed

        except Exception:
            return solution

    def __select_program_for_removal(
        self,
        solution: Solution,
        instance: InstanceData,
    ) -> ScheduledProgram | None:
        """
        GLS-guided remove selection.

        Këtu nuk vendos remove operatori.
        Këtu vendos vetë GLS cilin program me largu.

        Programet me:
        - penalty të lartë,
        - score të ulët,
        - bonus të ulët,
        - ndikim negativ në switching,
        - dhe gap potencial të mirë
        kanë më shumë gjasë të largohen.
        """
        scheduled = self.__sorted_schedule(solution.selected.scheduled_programs)

        if not scheduled:
            return None

        candidates = []

        for index, scheduled_program in enumerate(scheduled):
            feature = self.__feature_of(scheduled_program)

            penalty = self.penalties[feature]
            value = self.__program_value(scheduled_program, instance)
            switch_gain = self.__switch_gain_if_removed(scheduled, index, instance)
            gap_potential = self.__gap_potential_if_removed(scheduled, index, instance)

            # Sa më i lartë removal_score, aq më i përshtatshëm për largim.
            removal_score = (
                3.0 * penalty
                + 0.20 * switch_gain
                + 0.03 * gap_potential
                - 0.10 * value
            )

            candidates.append((scheduled_program, removal_score))

        # Mos e zgjedh gjithmonë të parin, sepse bëhet shumë greedy.
        # Merr top-k kandidatët dhe zgjedh probabilistikisht.
        candidates.sort(key=lambda x: x[1], reverse=True)

        top_k = min(5, len(candidates))
        top_candidates = candidates[:top_k]

        min_score = min(score for _, score in top_candidates)
        weights = [(score - min_score + 1.0) for _, score in top_candidates]

        selected = random.choices(
            [program for program, _ in top_candidates],
            weights=weights,
            k=1,
        )[0]

        return selected

    def __should_accept(
        self,
        current: Solution,
        neighbor: Solution,
        best: Solution,
    ) -> bool:
        """
        Acceptance më i kontrolluar.

        E pranon neighbor-in nëse:
        1. përmirëson fitness normal
        2. ose përmirëson adjusted quality, por nuk bie shumë poshtë best-it
        """
        if neighbor.fitness >= current.fitness:
            return True

        allowed_min_fitness = best.fitness * (1.0 - self.acceptance_drop_ratio)

        if neighbor.fitness < allowed_min_fitness:
            return False

        return self.__adjusted_quality(neighbor) > self.__adjusted_quality(current)

    def __intensify(self, instance: InstanceData, solution: Solution) -> Solution:
        """
        Stronger improvement phase:
        tries insert and replace several times.
        """
        current = deepcopy(solution)

        for _ in range(3):
            inserted = insert_best(deepcopy(current), instance)

            if inserted.fitness >= current.fitness:
                current = inserted

        for _ in range(3):
            replaced = replace(deepcopy(current), instance)

            if replaced.fitness >= current.fitness:
                current = replaced

        return current

    def __restart_from_best(self, instance: InstanceData, best: Solution) -> Solution:
        """
        Restart near the best solution, not from a random weak solution.
        """
        current = deepcopy(best)

        perturbations = random.randint(2, 5)

        for _ in range(perturbations):
            program_to_remove = self.__select_program_for_removal(current, instance)

            if program_to_remove is None:
                continue

            current = remove(current, program_to_remove)
            current = insert_best(deepcopy(current), instance)

        return current

    def __adjusted_quality(self, solution: Solution) -> float:
        """
        Maximization:
        adjusted_quality = fitness - beta * penalty_sum
        """
        penalty_sum = 0

        for feature in self.__features(solution):
            penalty_sum += self.penalties[feature]

        return solution.fitness - self.beta * penalty_sum

    def __update_penalties(self, solution: Solution):
        """
        Penalize most penalizable features in current solution.
        """
        features = self.__features(solution)

        if not features:
            return

        utilities = {}

        for feature in features:
            value = self.__feature_cost(feature)
            penalty = self.penalties[feature]

            # For maximization:
            # lower value + lower previous penalty = more penalizable.
            utilities[feature] = 1.0 / ((1.0 + penalty) * value)

        max_utility = max(utilities.values())

        for feature, utility in utilities.items():
            if utility == max_utility:
                self.penalties[feature] += 1

    def __features(self, solution: Solution) -> list[tuple]:
        return [
            self.__feature_of(scheduled_program)
            for scheduled_program in solution.selected.scheduled_programs
        ]

    def __feature_of(self, scheduled_program: ScheduledProgram) -> tuple:
        return (
            scheduled_program.channel_id,
            scheduled_program.program_id,
        )

    def __feature_cost(self, feature: tuple) -> float:
        program = self.program_lookup.get(feature)

        if program is None:
            return 1.0

        return max(1.0, float(program.score))

    def __program_value(
        self,
        scheduled_program: ScheduledProgram,
        instance: InstanceData,
    ) -> float:
        feature = self.__feature_of(scheduled_program)
        program = self.program_lookup.get(feature)

        if program is None:
            return 1.0

        duration = max(1, scheduled_program.end - scheduled_program.start)
        original_duration = max(1, program.end - program.start)

        duration_ratio = duration / original_duration
        base_score = float(program.score) * duration_ratio

        bonus = self.__time_preference_bonus(scheduled_program, program.genre, instance)

        return max(1.0, base_score + bonus)

    def __time_preference_bonus(
        self,
        scheduled_program: ScheduledProgram,
        genre: str,
        instance: InstanceData,
    ) -> float:
        total_bonus = 0.0

        for preference in instance.time_preferences:
            if preference.preferred_genre != genre:
                continue

            overlap = min(scheduled_program.end, preference.end) - max(
                scheduled_program.start,
                preference.start,
            )

            if overlap > 0:
                total_bonus += preference.bonus

        return total_bonus

    def __switch_gain_if_removed(
        self,
        schedule: list[ScheduledProgram],
        index: int,
        instance: InstanceData,
    ) -> float:
        current = schedule[index]

        left = schedule[index - 1] if index > 0 else None
        right = schedule[index + 1] if index < len(schedule) - 1 else None

        old_switches = 0
        new_switches = 0

        if left is not None and left.channel_id != current.channel_id:
            old_switches += 1

        if right is not None and current.channel_id != right.channel_id:
            old_switches += 1

        if left is not None and right is not None and left.channel_id != right.channel_id:
            new_switches += 1

        reduced_switches = old_switches - new_switches

        return reduced_switches * instance.switch_penalty

    def __gap_potential_if_removed(
        self,
        schedule: list[ScheduledProgram],
        index: int,
        instance: InstanceData,
    ) -> int:
        left_end = instance.opening_time if index == 0 else schedule[index - 1].end
        right_start = instance.closing_time if index == len(schedule) - 1 else schedule[index + 1].start

        return max(0, right_start - left_end)

    def __estimate_beta(self, solution: Solution) -> float:
        number_of_features = max(1, len(solution.selected.scheduled_programs))
        return self.alpha * solution.fitness / number_of_features

    def __sorted_schedule(
        self,
        schedule: list[ScheduledProgram],
    ) -> list[ScheduledProgram]:
        return sorted(
            schedule,
            key=lambda program: (
                program.start,
                program.end,
                program.channel_id,
                program.program_id,
            ),
        )