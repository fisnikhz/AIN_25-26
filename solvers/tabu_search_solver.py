import random
from collections import deque, defaultdict
from copy import deepcopy
from typing import Optional

from solvers.base_solver import BaseSolver
from models.instance.instance_data import InstanceData
from models.solution.solution import Solution
from operators.swap import swap
from operators.shift_borders import shift_borders, TargetBorder, Mode
from operators.replace import replace
from operators.insert import insert_best
import config.tabu_search_config as config


class TabuSearchSolver(BaseSolver):

    def __init__(self, solution: Solution, instance: InstanceData):
        super().__init__(solution)
        self.instance = instance

        self.tabu_list = deque(maxlen=config.TABU_TENURE)
        self.frequency_memory = defaultdict(int)
        self.best_ever = deepcopy(solution)
        self.elite_solutions = [(solution.fitness, deepcopy(solution))]
        self.diversification_mode = False
        self.diversification_remaining = 0

        self.candidate_pool = self._build_candidate_pool(solution)
        print(f"Candidate pool: {len(self.candidate_pool)} / {len(solution.unselected_ids)} unselected programs")

        self.stats = {
            'iterations': 0,
            'improvements': 0,
            'aspiration_objective_hits': 0,
            'aspiration_default_hits': 0,
            'diversifications': 0,
            'elite_restarts': 0,
        }

    def solve(self) -> Solution:
        current = deepcopy(self.solution)
        no_improve_count = 0

        print("\n" + "=" * 60)
        print("TABU SEARCH")
        print("=" * 60)
        print(f"Initial fitness:          {current.fitness}")
        print(f"Tabu tenure:              {config.TABU_TENURE}")
        print(f"Neighborhood size:        {config.NEIGHBORHOOD_SIZE}")
        print(f"Max iterations:           {config.MAX_ITERATIONS}")
        print(f"Patience:                 {config.PATIENCE}")
        print(f"Diversification trigger:  {config.DIVERSIFICATION_TRIGGER}")
        print(f"Intensification trigger:  {config.INTENSIFICATION_TRIGGER}")

        while (self.stats['iterations'] < config.MAX_ITERATIONS and
               no_improve_count < config.PATIENCE):

            iteration = self.stats['iterations']

            neighbors = self._generate_neighbors(current)
            if not neighbors:
                break

            scored = [(self._score(n, m), n, m) for n, m in neighbors]
            scored.sort(key=lambda x: -x[0])

            _, best_neighbor, best_move = scored[0]
            non_tabu = [(s, n, m) for s, n, m in scored if not self._is_tabu(m)]

            if not self._is_tabu(best_move):
                current = best_neighbor
                applied_move = best_move
            elif best_neighbor.fitness > self.best_ever.fitness:
                current = best_neighbor
                applied_move = best_move
                self.stats['aspiration_objective_hits'] += 1
            elif non_tabu:
                _, best_non_tabu, best_nt_move = non_tabu[0]
                current = best_non_tabu
                applied_move = best_nt_move
            else:
                current = best_neighbor
                applied_move = best_move
                self.stats['aspiration_default_hits'] += 1

            self.tabu_list.append(applied_move)
            self.frequency_memory[applied_move] += 1

            if current.fitness > self.best_ever.fitness:
                self.best_ever = deepcopy(current)
                no_improve_count = 0
                self.stats['improvements'] += 1
                print(f"[Iter {iteration}] NEW BEST: {self.best_ever.fitness:.2f}")
            else:
                no_improve_count += 1

            self._update_elite(current)

            if self.diversification_mode:
                self.diversification_remaining -= 1
                if self.diversification_remaining <= 0:
                    self.diversification_mode = False

            if no_improve_count == config.DIVERSIFICATION_TRIGGER:
                self.diversification_mode = True
                self.diversification_remaining = config.DIVERSIFICATION_DURATION
                self.stats['diversifications'] += 1
                print(f"[Iter {iteration}] DIVERSIFICATION mode ON (frequency penalty active)")

            if no_improve_count == config.INTENSIFICATION_TRIGGER:
                current = self._intensify_from_elite()
                no_improve_count = 0
                self.stats['elite_restarts'] += 1
                print(f"[Iter {iteration}] ELITE RESTART → fitness {current.fitness:.2f}")

            self.stats['iterations'] += 1

            if self.stats['iterations'] % 50 == 0:
                mode_str = "DIVERSIFY" if self.diversification_mode else "NORMAL"
                print(f"[Iter {self.stats['iterations']:>4}] Best: {self.best_ever.fitness:.2f} | "
                      f"Current: {current.fitness:.2f} | Mode: {mode_str} | NoImprove: {no_improve_count}")

        self._print_stats()
        return self.best_ever

    def _score(self, neighbor: Solution, move) -> float:
        base = neighbor.fitness
        if self.diversification_mode:
            return base - config.DIVERSITY_WEIGHT * self.frequency_memory[move]
        return base

    def _build_candidate_pool(self, solution: Solution) -> set:
        scheduled = solution.selected.scheduled_programs
        unselected_set = set(solution.unselected_ids)

        gaps_by_channel = {}
        for channel in self.instance.channels:
            ch_id = channel.channel_id
            ch_progs = sorted(
                [sp for sp in scheduled if sp.channel_id == ch_id],
                key=lambda x: x.start
            )
            gaps = []
            cursor = self.instance.opening_time
            for sp in ch_progs:
                if sp.start > cursor:
                    gaps.append((cursor, sp.start))
                cursor = max(cursor, sp.end)
            if cursor < self.instance.closing_time:
                gaps.append((cursor, self.instance.closing_time))
            gaps_by_channel[ch_id] = gaps

        candidates = set()
        for channel in self.instance.channels:
            ch_id = channel.channel_id
            channel_gaps = gaps_by_channel.get(ch_id, [])
            if not channel_gaps:
                continue
            for program in channel.programs:
                if program.program_id not in unselected_set:
                    continue
                if (program.end - program.start) < self.instance.min_duration:
                    continue
                for g_start, g_end in channel_gaps:
                    overlap = min(program.end, g_end) - max(program.start, g_start)
                    if overlap >= self.instance.min_duration:
                        candidates.add(program.program_id)
                        break

        return candidates

    def _slim(self, solution: Solution) -> Solution:
        s = deepcopy(solution)
        s.unselected_ids = [uid for uid in solution.unselected_ids
                            if uid in self.candidate_pool]
        return s

    def _generate_neighbors(self, solution: Solution) -> list:
        slim = self._slim(solution)

        neighbors = []
        operators = ['swap', 'shift', 'replace']
        if len(slim.unselected_ids) <= config.MAX_UNSELECTED_FOR_INSERT:
            operators.append('insert')

        for _ in range(config.NEIGHBORHOOD_SIZE):
            op = random.choice(operators)
            try:
                if op == 'swap':
                    result = self._neighbor_swap(slim)
                elif op == 'shift':
                    result = self._neighbor_shift(slim)
                elif op == 'replace':
                    result = self._neighbor_replace(slim)
                else:
                    result = self._neighbor_insert(slim)

                if result is not None:
                    neighbors.append(result)
            except Exception:
                continue

        return neighbors

    def _neighbor_swap(self, solution: Solution) -> Optional[tuple]:
        scheduled = list(solution.selected.scheduled_programs)
        if len(scheduled) < 2:
            return None
        p1, p2 = random.sample(scheduled, 2)
        neighbor = swap(self.instance, solution, p1, p2)
        if neighbor is solution:
            return None
        move = ("swap", frozenset([p1.program_id, p2.program_id]))
        return neighbor, move

    def _neighbor_shift(self, solution: Solution) -> Optional[tuple]:
        scheduled = list(solution.selected.scheduled_programs)
        if not scheduled:
            return None
        program = random.choice(scheduled)
        direction = random.choice(list(TargetBorder))
        mode = random.choice(list(Mode))
        shamt = random.randint(1, config.MAX_SHIFT)
        neighbor = shift_borders(self.instance, solution, program, mode, direction, shamt)
        if neighbor is solution:
            return None
        move = ("shift", program.program_id, str(direction))
        return neighbor, move

    def _neighbor_replace(self, solution: Solution) -> Optional[tuple]:
        before_ids = {p.program_id for p in solution.selected.scheduled_programs}
        neighbor = replace(solution, self.instance)
        after_ids = {p.program_id for p in neighbor.selected.scheduled_programs}

        removed = before_ids - after_ids
        added = after_ids - before_ids
        if not removed or not added:
            return None

        move = ("replace", frozenset([list(removed)[0], list(added)[0]]))
        return neighbor, move

    def _neighbor_insert(self, solution: Solution) -> Optional[tuple]:
        before_ids = {p.program_id for p in solution.selected.scheduled_programs}
        neighbor = insert_best(solution, self.instance)
        after_ids = {p.program_id for p in neighbor.selected.scheduled_programs}

        added = after_ids - before_ids
        if not added:
            return None

        move = ("insert", list(added)[0])
        return neighbor, move

    def _is_tabu(self, move) -> bool:
        return move in self.tabu_list

    def _update_elite(self, solution: Solution):
        if any(abs(f - solution.fitness) < 0.001 for f, _ in self.elite_solutions):
            return
        self.elite_solutions.append((solution.fitness, deepcopy(solution)))
        self.elite_solutions.sort(key=lambda x: -x[0])
        self.elite_solutions = self.elite_solutions[:config.ELITE_SIZE]

    def _intensify_from_elite(self) -> Solution:
        top = self.elite_solutions[:min(3, len(self.elite_solutions))]
        _, elite = random.choice(top)
        return deepcopy(elite)

    def _print_stats(self):
        print("\n" + "=" * 60)
        print("TABU SEARCH - FINAL STATISTICS")
        print("=" * 60)
        print(f"Best Fitness:              {self.best_ever.fitness:.2f}")
        print(f"Total Iterations:          {self.stats['iterations']}")
        print(f"Improvements:              {self.stats['improvements']}")
        print(f"Aspiration #1 (objective): {self.stats['aspiration_objective_hits']}")
        print(f"Aspiration #2 (all tabu):  {self.stats['aspiration_default_hits']}")
        print(f"Diversifications:          {self.stats['diversifications']}")
        print(f"Elite Restarts:            {self.stats['elite_restarts']}")
        print(f"Unique Moves Seen:         {len(self.frequency_memory)}")
        print(f"Elite Solutions Retained:  {len(self.elite_solutions)}")
