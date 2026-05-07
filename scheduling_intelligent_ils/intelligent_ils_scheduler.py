from collections import defaultdict
from copy import deepcopy
from bisect import bisect_right
import heapq
import random
import time

import config.classic_ils_config as config
from models.instance.instance_data import InstanceData
from models.solution.schedule import Schedule
from models.solution.scheduled_program import ScheduledProgram
from models.solution.solution import Solution
from operators.insert import insert_best
from operators.replace import replace
from operators.shift_borders import Mode, TargetBorder, shift_borders
from operators.swap import swap
from solvers.base_solver import BaseSolver


class IntelligentILSSolver(BaseSolver):
    def __init__(self, solution: Solution):
        super().__init__(solution)
        self.visited = set()
        self.deadline = None
        self.large_instance = False
        self.total_programs = 0

    def solve(self, instance: InstanceData) -> Solution:
        print("\n=== Intelligent Iterated Local Search ===")
        self._setup(instance)

        current = self._polish(instance, deepcopy(self.solution))
        if not self.large_instance:
            current = self._local_search(instance, current)
            current = self._intensify(instance, current)

        best = deepcopy(current)
        self.visited = {self._signature(best)}
        max_iter = min(getattr(config, "MAX_ITERATIONS", 200), 120 if self.large_instance else 90)
        stuck = 0

        for iteration in range(max_iter):
            if self._time_expired():
                print("[STOP] Time limit reached.")
                break
            if iteration % 10 == 0:
                print(f"[ILS] Iter {iteration} | Best fitness: {best.fitness}")

            candidate = self._perturb(instance, current)
            candidate = self._local_search(instance, candidate)
            candidate = self._polish(instance, candidate)

            if iteration > 0 and iteration % getattr(config, "INSERTION_INTERVAL", 50) == 0 and not self.large_instance:
                candidate = self._intensify(instance, candidate)

            if candidate.fitness >= current.fitness or random.random() < 0.08:
                current = candidate
            self.visited.add(self._signature(current))

            if current.fitness > best.fitness:
                print(f"[BEST] {best.fitness} -> {current.fitness}")
                best = deepcopy(current)
                stuck = 0
            else:
                stuck += 1

            stop_after = 55 if self.large_instance else 25
            if stuck >= stop_after:
                print(f"[STOP] No improvement for {stop_after} iterations.")
                break

        best = self._reoptimize(instance, best)
        print(f"\nFINAL BEST FITNESS: {best.fitness}")
        return best

    def _setup(self, instance: InstanceData):
        self.total_programs = sum(len(channel.programs) for channel in instance.channels)
        selected = len(self.solution.selected.scheduled_programs)
        self.large_instance = self.total_programs > 3000 or selected > 70
        limit = getattr(config, "INTELLIGENT_ILS_TIME_LIMIT", 30 if self.large_instance else 45)
        self.deadline = time.perf_counter() + limit

    def _local_search(self, instance: InstanceData, solution: Solution) -> Solution:
        current = solution
        no_improve = 0
        limit = 1 if self.large_instance else getattr(config, "LOCAL_SEARCH_ITERATIONS", 20)

        for _ in range(limit):
            if self._time_expired():
                break

            neighbor = self._mutate(instance, deepcopy(current))
            visited_before = self._signature(neighbor) in self.visited

            if visited_before and neighbor.fitness <= current.fitness:
                no_improve += 1
            elif neighbor.fitness >= current.fitness:
                no_improve = 0 if neighbor.fitness > current.fitness else no_improve
                current = neighbor
            else:
                no_improve += 1

            if no_improve >= 8:
                break
        return current

    def _perturb(self, instance: InstanceData, solution: Solution) -> Solution:
        result = deepcopy(solution)
        strength = 1 if self.large_instance else min(getattr(config, "PERTURBATION_STRENGTH", 3), 3)

        for _ in range(strength):
            if self._time_expired():
                break
            result = self._mutate(instance, result)
        return result

    def _mutate(self, instance: InstanceData, solution: Solution) -> Solution:
        scheduled = solution.selected.scheduled_programs
        if not scheduled:
            return solution

        candidates = []
        focus = self._weak_program(solution)
        amount = random.randint(1, getattr(config, "MAX_SHIFT", 10))
        moves = [(mode, border) for mode in Mode for border in TargetBorder]
        if self.large_instance:
            moves = random.sample(moves, 1)

        try:
            for mode, border in moves:
                moved = shift_borders(instance, solution, focus, mode, border, amount)
                if self._is_valid(moved, instance):
                    candidates.append(moved)

            if len(scheduled) >= 2 and not self.large_instance:
                partner = min(
                    (program for program in scheduled if program != focus),
                    key=lambda program: abs(program.start - focus.start) + abs(program.end - focus.end),
                )
                pairs = [(focus, partner), tuple(random.sample(scheduled, 2))]
                for first, second in pairs:
                    changed = swap(instance, solution, first, second)
                    if self._is_valid(changed, instance):
                        candidates.append(changed)

                changed = replace(deepcopy(solution), instance)
                if self._is_valid(changed, instance):
                    candidates.append(changed)
        except Exception:
            return solution

        new_candidates = [
            candidate for candidate in candidates
            if self._signature(candidate) not in self.visited or candidate.fitness > solution.fitness
        ]
        return max(new_candidates or candidates, key=lambda x: x.fitness) if candidates else solution

    def _intensify(self, instance: InstanceData, solution: Solution) -> Solution:
        inserted = insert_best(deepcopy(solution), instance)
        if inserted and self._is_valid(inserted, instance) and inserted.fitness > solution.fitness:
            return inserted

        best = solution
        for _ in range(3):
            candidate = replace(deepcopy(best), instance)
            if candidate and self._is_valid(candidate, instance) and candidate.fitness > best.fitness:
                best = candidate
        return best

    def _polish(self, instance: InstanceData, solution: Solution) -> Solution:
        if len(solution.selected.scheduled_programs) > 250:
            return solution

        best = deepcopy(solution)
        improved = True
        while improved and not self._time_expired():
            improved = False
            ordered = self._sort(best.selected.scheduled_programs)

            for index, program in enumerate(ordered):
                original = self._original(program)
                if original is None:
                    continue

                left_limit = instance.opening_time if index == 0 else ordered[index - 1].end
                right_limit = instance.closing_time if index + 1 == len(ordered) else ordered[index + 1].start
                windows = [
                    (max(original.start, left_limit), program.end),
                    (program.start, min(original.end, right_limit)),
                    (max(original.start, left_limit), min(original.end, right_limit)),
                ]

                for start, end in windows:
                    if (start, end) == (program.start, program.end):
                        continue

                    candidate = deepcopy(best)
                    target = self._find_same_program(candidate.selected.scheduled_programs, program)
                    target.start, target.end = start, end
                    candidate.selected.scheduled_programs = self._sort(candidate.selected.scheduled_programs)
                    candidate._fitness = None

                    if self._is_valid(candidate, instance) and candidate.fitness > best.fitness:
                        best, improved = candidate, True
                        break
                if improved:
                    break
        return best

    def _reoptimize(self, instance: InstanceData, solution: Solution) -> Solution:
        start_time = time.perf_counter()
        strategy = self._strategy(solution)
        candidate = None

        if strategy == "small":
            candidate = self._small_reoptimize(instance, solution)
        elif strategy == "large":
            candidate = self._large_reoptimize(instance, solution)

        if candidate and self._is_valid(candidate, instance) and candidate.fitness > solution.fitness:
            print(f"[REOPT] {solution.fitness} -> {candidate.fitness} ({time.perf_counter() - start_time:.1f}s)")
            return candidate
        return solution

    def _strategy(self, solution: Solution):
        selected = len(solution.selected.scheduled_programs)
        if self.total_programs <= 180 and selected >= 28:
            return "small"
        if (self.total_programs >= 3500 and 60 <= selected <= 120) or (self.total_programs >= 20000 and selected >= 500):
            return "large"
        return None

    def _small_reoptimize(self, instance: InstanceData, seed: Solution) -> Solution:
        states = [(0, instance.opening_time, None, None, 0, frozenset(), [])]
        best = states[0]

        for segment in self._candidate_segments(instance, seed):
            new_states = []
            for score, end, channel, genre, streak, used, sequence in states:
                if end > segment["start"] or segment["program_id"] in used:
                    continue

                next_streak = streak + 1 if genre == segment["genre"] else 1
                if next_streak > instance.max_consecutive_genre:
                    continue

                switch = 0 if channel is None or channel == segment["channel_id"] else instance.switch_penalty
                new_score = score + segment["value"] - switch
                state = (
                    new_score, segment["end"], segment["channel_id"], segment["genre"],
                    next_streak, used | {segment["program_id"]}, sequence + [segment],
                )
                new_states.append(state)
                if new_score > best[0]:
                    best = state

            if new_states:
                states = heapq.nlargest(50000, states + new_states, key=lambda state: (state[0], -state[1], len(state[6])))
        return self._solution_from_segments(instance, best[6])

    def _large_reoptimize(self, instance: InstanceData, seed: Solution) -> Solution:
        segments = self._candidate_segments(instance, seed)
        selected = len(seed.selected.scheduled_programs)
        best = seed

        if selected <= 1000 and self.total_programs < 50000:
            end_events = sorted((segment["end"], index) for index, segment in enumerate(segments))
            order = sorted(range(len(segments)), key=lambda index: (segments[index]["start"], segments[index]["end"]))
            active, by_end, nodes = {}, defaultdict(list), []
            best_score, best_node, end_pos = 0, None, 0

            for index in order:
                segment = segments[index]
                while end_pos < len(end_events) and end_events[end_pos][0] <= segment["start"]:
                    finished = end_events[end_pos][1]
                    for state, score, node in by_end[finished]:
                        if state not in active or score > active[state][0]:
                            active[state] = (score, node)
                    end_pos += 1

                base_score, previous_node, streak = self._best_previous(active, segment, instance)
                score, node = base_score + segment["value"], len(nodes)
                nodes.append((previous_node, segment))
                by_end[index].append(((segment["channel_id"], segment["genre"], streak), score, node))

                if score > best_score:
                    best_score, best_node = score, node

            candidate = self._solution_from_node(instance, nodes, best_node)
            if candidate and self._is_valid(candidate, instance) and candidate.fitness > best.fitness:
                best = candidate

        schedule = self._sort(best.selected.scheduled_programs)
        starts = [program.start for program in schedule]
        values = [self._local_value(program) for program in schedule]
        used = {program.program_id for program in schedule}
        best_fitness, best_solution = best.fitness, best

        for segment in segments:
            pos = bisect_right(starts, segment["start"])
            for index in range(max(0, pos - 2), min(len(schedule), pos + 3)):
                old = schedule[index]
                if segment["program_id"] in used and segment["program_id"] != old.program_id:
                    continue

                previous = schedule[index - 1] if index > 0 else None
                following = schedule[index + 1] if index + 1 < len(schedule) else None
                if previous and previous.end > segment["start"]:
                    continue
                if following and segment["end"] > following.start:
                    continue

                old_switch = (0 if not previous or previous.channel_id == old.channel_id else instance.switch_penalty)
                old_switch += 0 if not following or old.channel_id == following.channel_id else instance.switch_penalty
                new_switch = (0 if not previous or previous.channel_id == segment["channel_id"] else instance.switch_penalty)
                new_switch += 0 if not following or segment["channel_id"] == following.channel_id else instance.switch_penalty
                delta = segment["value"] - values[index] + old_switch - new_switch

                if best.fitness + delta <= best_fitness:
                    continue

                candidate_schedule = self._sort(
                    schedule[:index]
                    + [ScheduledProgram(segment["program_id"], segment["channel_id"], segment["start"], segment["end"])]
                    + schedule[index + 1:]
                )
                candidate = Solution(best.evaluator, Schedule(candidate_schedule), best.unselected_ids.copy())
                if self._is_valid(candidate, instance) and candidate.fitness > best_fitness:
                    used_ids = {program.program_id for program in candidate.selected.scheduled_programs}
                    candidate.unselected_ids = [p.program_id for c in instance.channels for p in c.programs if p.program_id not in used_ids]
                    best_fitness, best_solution = candidate.fitness, candidate

        return best_solution

    def _candidate_segments(self, instance: InstanceData, seed: Solution):
        seed_windows = [(p.program_id, p.channel_id, p.start, p.end) for p in seed.selected.scheduled_programs]
        time_points = {instance.opening_time, instance.closing_time}
        for pref in instance.time_preferences:
            time_points.update([pref.start, pref.end])
        for block in instance.priority_blocks:
            time_points.update([block.start, block.end])

        segments, seen = [], set()
        for channel in instance.channels:
            for program in channel.programs:
                left = max(program.start, instance.opening_time)
                right = min(program.end, instance.closing_time)
                windows = self._windows(instance, program, left, right, time_points)

                for program_id, channel_id, start, end in seed_windows:
                    if program_id == program.program_id and channel_id == channel.channel_id and left <= start < end <= right:
                        windows.add((start, end))

                for start, end in windows:
                    key = (program.program_id, channel.channel_id, start, end)
                    if key in seen or not self._valid_segment(instance, program, channel.channel_id, start, end):
                        continue
                    seen.add(key)
                    segments.append({
                        "program_id": program.program_id,
                        "channel_id": channel.channel_id,
                        "start": start,
                        "end": end,
                        "genre": program.genre,
                        "value": self._segment_value(instance, program, start, end),
                    })
        return sorted(segments, key=lambda x: (x["start"], x["end"], -x["value"]))

    def _windows(self, instance: InstanceData, program, left, right, time_points):
        windows = set()
        full_duration = program.end - program.start

        if right <= left:
            return windows
        if full_duration < instance.min_duration:
            return {(left, right)} if left == program.start and right == program.end else windows
        if right - left < instance.min_duration:
            return windows

        windows.update([(left, right), (left, left + instance.min_duration), (right - instance.min_duration, right)])
        for pref in instance.time_preferences:
            if program.genre == pref.preferred_genre:
                start, end = max(left, pref.start), min(right, pref.end)
                if end - start >= instance.min_duration:
                    windows.update([(start, end), (start, start + instance.min_duration), (end - instance.min_duration, end)])
        for point in time_points:
            if left <= point <= right:
                if point + instance.min_duration <= right:
                    windows.add((point, point + instance.min_duration))
                if left <= point - instance.min_duration:
                    windows.add((point - instance.min_duration, point))
        return windows

    def _segment_value(self, instance: InstanceData, program, start, end) -> float:
        value = float(program.score)
        for pref in instance.time_preferences:
            overlap = min(end, pref.end) - max(start, pref.start)
            if program.genre == pref.preferred_genre and overlap >= instance.min_duration:
                value += pref.bonus
        if start > program.start:
            value -= instance.termination_penalty
        if end < program.end:
            value -= instance.termination_penalty
        return value

    def _best_previous(self, active, segment, instance):
        best = (0, None, 1)
        for (channel, genre, streak), (score, node) in active.items():
            next_streak = streak + 1 if genre == segment["genre"] else 1
            if next_streak > instance.max_consecutive_genre:
                continue
            switch = 0 if channel == segment["channel_id"] else instance.switch_penalty
            if score - switch > best[0]:
                best = (score - switch, node, next_streak)
        return best

    def _solution_from_node(self, instance: InstanceData, nodes, node) -> Solution:
        sequence = []
        while node is not None:
            node, segment = nodes[node]
            sequence.append(segment)
        return self._solution_from_segments(instance, reversed(sequence))

    def _solution_from_segments(self, instance: InstanceData, segments) -> Solution:
        schedule = Schedule([
            ScheduledProgram(s["program_id"], s["channel_id"], s["start"], s["end"])
            for s in segments
        ])
        used = {program.program_id for program in schedule}
        unselected = [p.program_id for c in instance.channels for p in c.programs if p.program_id not in used]
        return Solution(self.solution.evaluator, schedule, unselected)

    def _is_valid(self, solution: Solution, instance: InstanceData) -> bool:
        if not solution or not solution.selected.scheduled_programs:
            return True

        last_end, last_genre, genre_count = None, None, 0
        for program in self._sort(solution.selected.scheduled_programs):
            original = self._original(program)
            if original is None or not self._valid_segment(instance, original, program.channel_id, program.start, program.end):
                return False
            if last_end is not None and last_end > program.start:
                return False

            genre_count = genre_count + 1 if original.genre == last_genre else 1
            last_genre = original.genre
            if genre_count > instance.max_consecutive_genre:
                return False
            last_end = program.end
        return True

    def _valid_segment(self, instance: InstanceData, program, channel_id, start, end) -> bool:
        duration = end - start
        original_duration = program.end - program.start
        if start < instance.opening_time or end > instance.closing_time or start >= end:
            return False
        if start < program.start or end > program.end:
            return False
        if original_duration < instance.min_duration and duration != original_duration:
            return False
        if original_duration >= instance.min_duration and duration < instance.min_duration:
            return False
        return all(
            channel_id in block.allowed_channels
            for block in instance.priority_blocks
            if min(end, block.end) > max(start, block.start)
        )

    def _weak_program(self, solution: Solution):
        scheduled = solution.selected.scheduled_programs
        sample = scheduled if not self.large_instance else random.sample(scheduled, min(8, len(scheduled)))
        return min(sample, key=self._local_value)

    def _local_value(self, scheduled_program: ScheduledProgram) -> float:
        original = self._original(scheduled_program)
        return self._segment_value(self.solution.evaluator.instance, original, scheduled_program.start, scheduled_program.end)

    def _original(self, scheduled_program: ScheduledProgram):
        try:
            return self.solution.evaluator.get_original_program(scheduled_program.channel_id, scheduled_program.program_id)
        except KeyError:
            return None

    def _find_same_program(self, schedule, target):
        return next(
            program for program in schedule
            if program.channel_id == target.channel_id
            and program.program_id == target.program_id
            and program.start == target.start
            and program.end == target.end
        )

    def _sort(self, schedule):
        return sorted(schedule, key=lambda x: (x.start, x.end, x.channel_id, x.program_id))

    def _signature(self, solution: Solution):
        return tuple(
            (p.channel_id, p.program_id, p.start, p.end)
            for p in self._sort(solution.selected.scheduled_programs)
        )

    def _time_expired(self) -> bool:
        return self.deadline is not None and time.perf_counter() >= self.deadline
