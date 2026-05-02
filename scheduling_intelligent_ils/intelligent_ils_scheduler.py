from __future__ import annotations

import random
from pathlib import Path
from typing import Optional

from scheduling_intelligent_ils.common import (
    CandidateSegment,
    CandidateSolution,
    InstanceContext,
    load_candidate_solution,
)


class AdaptiveHybridILSScheduler:
    def __init__(
        self,
        instance_data,
        random_seed: int = 20260413,
        max_iterations: Optional[int] = None,
        verbose: bool = False,
        beam_seed_path: Optional[str | Path] = None,
        dps_seed_path: Optional[str | Path] = None,
    ):
        self.instance_data = instance_data
        self.context = InstanceContext(instance_data)
        self.random = random.Random(random_seed)
        self.verbose = verbose

        self.beam_seed_path = Path(beam_seed_path) if beam_seed_path else None
        self.dps_seed_path = Path(dps_seed_path) if dps_seed_path else None

        total_programs = sum(len(channel.programs) for channel in instance_data.channels)
        self.include_instance_candidates = total_programs <= 9000
        self.polish_window_sizes: list[int] = []

        if total_programs <= 300:
            self.max_iterations = 35
            self.window_beam_width = 1000
            self.block_size = 4
            self.window_candidate_limit = 1000
            self.polish_window_sizes = [1, 2, 3, 4, 5]

        elif total_programs <= 2500:
            self.max_iterations = 28
            self.window_beam_width = 22
            self.block_size = 4
            self.window_candidate_limit = 140

        elif total_programs <= 9000:
            self.max_iterations = 20
            self.window_beam_width = 16
            self.block_size = 3
            self.window_candidate_limit = 100

        else:
            self.max_iterations = 14
            self.window_beam_width = 10
            self.block_size = 2
            self.window_candidate_limit = 70
            if total_programs <= 25000:
                self.polish_window_sizes = [1]

        if max_iterations is not None:
            self.max_iterations = max_iterations

        self.catalog: list[CandidateSegment] = []
        self.catalog_time_points: set[int] = set()
        self.elite_pool: list[CandidateSolution] = []
        self.elite_size = 5

    def generate_solution(self) -> CandidateSolution:
        beam_seed, dps_seed = self._create_initial_solutions()

        self._build_catalog([beam_seed, dps_seed])

        if beam_seed.total_score >= dps_seed.total_score:
            current = beam_seed.clone()
            guide = dps_seed
            best_seed_name = "beam_search"
            alternative_seed_name = "dp_segmenting"
        else:
            current = dps_seed.clone()
            guide = beam_seed
            best_seed_name = "dp_segmenting"
            alternative_seed_name = "beam_search"

        best = current.clone()
        self._save_elite(best)

        stagnation = 0

        if self.verbose:
            print("\n=== Intelligent ILS from Existing Seeds ===")
            print(f"Beam seed score: {beam_seed.total_score}")
            print(f"DP-S seed score: {dps_seed.total_score}")
            print(f"Best seed: {best_seed_name}")
            print(f"Alternative seed: {alternative_seed_name}")
            print(f"Initial best score: {best.total_score}")
            print(f"Max iterations: {self.max_iterations}")

        for iteration in range(self.max_iterations):
            if self.verbose:
                print(
                    f"[ILS] iter={iteration} | "
                    f"current={current.total_score} | "
                    f"best={best.total_score} | "
                    f"stagnation={stagnation}"
                )

            active_guide = guide
            if iteration % 3 == 2 and self.elite_pool:
                active_guide = self.elite_pool[0]

            candidate = self._improve_solution(
                solution=current,
                guide=active_guide,
                stagnation=stagnation,
            )

            if candidate.total_score > best.total_score:
                best = candidate.clone()
                current = candidate.clone()
                self._save_elite(best)
                stagnation = 0

                if self.verbose:
                    print(f"[BEST] New best score: {best.total_score}")

                continue

            if candidate.total_score >= current.total_score:
                current = candidate.clone()

            elif self._accept_worse_solution(candidate, current, stagnation):
                current = candidate.clone()

            stagnation += 1

            if stagnation >= 8 and self.elite_pool:
                current = self.random.choice(self.elite_pool).clone()
                stagnation = 0

                if self.verbose:
                    print("[RESTART] Restarting from elite pool.")

        polished = self._polish_solution(best, guide)
        if polished.total_score > best.total_score:
            best = polished.clone()

            if self.verbose:
                print(f"[POLISH] Improved best score to: {best.total_score}")

        best.metadata["beam_seed_score"] = beam_seed.total_score
        best.metadata["dps_seed_score"] = dps_seed.total_score
        best.metadata["initial_score"] = max(beam_seed.total_score, dps_seed.total_score)
        best.metadata["best_seed"] = best_seed_name
        best.metadata["alternative_seed"] = alternative_seed_name
        best.metadata["beam_seed_path"] = str(self.beam_seed_path)
        best.metadata["dps_seed_path"] = str(self.dps_seed_path)
        best.metadata["improvement_over_best_seed"] = (
            best.total_score - max(beam_seed.total_score, dps_seed.total_score)
        )

        return best

    def _create_initial_solutions(self) -> tuple[CandidateSolution, CandidateSolution]:
        if self.beam_seed_path is None:
            raise ValueError(
                "Beam Search seed path is missing. "
                "Pass beam_seed_path when creating AdaptiveHybridILSScheduler."
            )

        if self.dps_seed_path is None:
            raise ValueError(
                "DP-S seed path is missing. "
                "Pass dps_seed_path when creating AdaptiveHybridILSScheduler."
            )

        beam_solution = load_candidate_solution(
            self.instance_data,
            self.beam_seed_path,
            source="beam_existing_seed",
        )

        dps_solution = load_candidate_solution(
            self.instance_data,
            self.dps_seed_path,
            source="dps_existing_seed",
        )

        return beam_solution, dps_solution

    def _build_catalog(self, solutions: list[CandidateSolution]) -> None:
        self.catalog = []
        self.catalog_time_points = self._collect_seed_time_points(solutions)
        seen = set()

        for solution in solutions:
            for segment in solution.scheduled_programs:
                self._add_catalog_item(segment, seen)

        self._add_seed_variants(solutions, seen)
        if self.include_instance_candidates:
            self._add_instance_candidates(seen)

        self.catalog.sort(
            key=lambda item: (
                item.start,
                item.end,
                item.channel_id,
                str(item.program_id),
            )
        )

    def _collect_seed_time_points(self, solutions: list[CandidateSolution]) -> set[int]:
        time_points = {self.context.opening_time, self.context.closing_time}

        for solution in solutions:
            for segment in solution.scheduled_programs:
                time_points.add(segment.start)
                time_points.add(segment.end)

        for pref in self.context.time_preferences:
            time_points.add(pref.start)
            time_points.add(pref.end)

        for block_start, block_end, _ in self.context.priority_blocks:
            time_points.add(block_start)
            time_points.add(block_end)

        return {
            time_point
            for time_point in time_points
            if self.context.opening_time <= time_point <= self.context.closing_time
        }

    def _add_catalog_item(self, segment: CandidateSegment, seen: set) -> None:
        signature = segment.signature()

        if signature in seen:
            return

        is_valid, _ = self.context.is_valid_segment(segment)
        if not is_valid:
            return

        seen.add(signature)
        self.catalog.append(segment)

    def _add_seed_variants(self, solutions: list[CandidateSolution], seen: set) -> None:
        seed_segments = {}

        for solution in solutions:
            for segment in solution.scheduled_programs:
                seed_segments[segment.unique_program_id] = segment

        for segment in seed_segments.values():
            channel_id, program = self.context.unique_program_lookup[segment.unique_program_id]

            for start, end in self._variant_windows(program, segment):
                variant = self.context.create_segment(
                    channel_id=channel_id,
                    program=program,
                    start=start,
                    end=end,
                    source=f"{segment.source}_variant",
                )
                self._add_catalog_item(variant, seen)

    def _add_instance_candidates(self, seen: set) -> None:
        for channel in self.instance_data.channels:
            for program in channel.programs:
                for start, end in self._variant_windows(program):
                    segment = self.context.create_segment(
                        channel_id=channel.channel_id,
                        program=program,
                        start=start,
                        end=end,
                        source="instance_candidate",
                    )
                    self._add_catalog_item(segment, seen)

    def _variant_windows(
        self,
        program,
        seed_segment: Optional[CandidateSegment] = None,
    ) -> list[tuple[int, int]]:
        left = max(program.start, self.context.opening_time)
        right = min(program.end, self.context.closing_time)
        min_duration = self.context.min_duration

        if right <= left:
            return []

        windows = {(left, right)}
        interesting_times = set()

        if seed_segment is not None:
            windows.add((seed_segment.start, seed_segment.end))
            interesting_times.update({seed_segment.start, seed_segment.end})
            if right - seed_segment.start >= min_duration:
                windows.add((seed_segment.start, right))
            if seed_segment.end - left >= min_duration:
                windows.add((left, seed_segment.end))

        full_duration = program.end - program.start
        if full_duration < min_duration:
            return sorted(windows)

        if right - left >= min_duration:
            windows.add((left, left + min_duration))
            windows.add((right - min_duration, right))

        for pref in self.context.time_preferences:
            if program.genre != pref.preferred_genre:
                continue

            pref_start = max(left, pref.start)
            pref_end = min(right, pref.end)
            if pref_end - pref_start >= min_duration:
                windows.add((pref_start, pref_end))
                interesting_times.update({pref_start, pref_end})

        for block_start, block_end, _ in self.context.priority_blocks:
            interesting_times.update({block_start, block_end})

        for time_point in self.catalog_time_points:
            if left <= time_point <= right:
                interesting_times.add(time_point)

        for time_point in interesting_times:
            if left <= time_point <= right - min_duration:
                windows.add((time_point, time_point + min_duration))
            if left + min_duration <= time_point <= right:
                windows.add((time_point - min_duration, time_point))
            if right - time_point >= min_duration:
                windows.add((time_point, right))
            if time_point - left >= min_duration:
                windows.add((left, time_point))

        return sorted(
            (start, end)
            for start, end in windows
            if left <= start < end <= right
        )

    def _save_elite(self, solution: CandidateSolution) -> None:
        signature = solution.signature()

        for elite in self.elite_pool:
            if elite.signature() == signature:
                return

        self.elite_pool.append(solution.clone())
        self.elite_pool.sort(key=lambda item: item.total_score, reverse=True)

        if len(self.elite_pool) > self.elite_size:
            self.elite_pool = self.elite_pool[: self.elite_size]

    def _improve_solution(
        self,
        solution: CandidateSolution,
        guide: CandidateSolution,
        stagnation: int,
    ) -> CandidateSolution:
        if not solution.scheduled_programs:
            return solution

        best = solution.clone()

        dynamic_block_size = self.block_size + stagnation
        dynamic_block_size = min(dynamic_block_size, len(solution.scheduled_programs))

        weak_index = self._find_weakest_program_index(solution)

        start_index, end_index = self._window_around(
            center=weak_index,
            size=dynamic_block_size,
            total=len(solution.scheduled_programs),
        )

        repaired = self._repair_window(
            solution=solution,
            start_index=start_index,
            end_index=end_index,
            guide=guide,
        )

        if repaired.total_score > best.total_score:
            best = repaired

        if stagnation >= 3:
            random_start = self.random.randint(
                0,
                max(0, len(solution.scheduled_programs) - dynamic_block_size),
            )

            random_end = random_start + dynamic_block_size

            repaired_random = self._repair_window(
                solution=solution,
                start_index=random_start,
                end_index=random_end,
                guide=guide,
            )

            if repaired_random.total_score > best.total_score:
                best = repaired_random

        if stagnation >= 4:
            wide_size = min(len(solution.scheduled_programs), dynamic_block_size * 2)
            wide_start, wide_end = self._window_around(
                center=weak_index,
                size=wide_size,
                total=len(solution.scheduled_programs),
            )
            repaired_wide = self._repair_window(
                solution=solution,
                start_index=wide_start,
                end_index=wide_end,
                guide=guide,
            )

            if repaired_wide.total_score > best.total_score:
                best = repaired_wide

        if stagnation >= 6:
            tail_start = max(0, weak_index - 1)
            repaired_tail = self._repair_window(
                solution=solution,
                start_index=tail_start,
                end_index=len(solution.scheduled_programs),
                guide=guide,
            )

            if repaired_tail.total_score > best.total_score:
                best = repaired_tail

            repaired_full = self._repair_window(
                solution=solution,
                start_index=0,
                end_index=len(solution.scheduled_programs),
                guide=guide,
            )

            if repaired_full.total_score > best.total_score:
                best = repaired_full

        return best

    def _polish_solution(
        self,
        solution: CandidateSolution,
        guide: Optional[CandidateSolution],
    ) -> CandidateSolution:
        if not self.polish_window_sizes:
            return solution

        current = solution.clone()
        improved = True

        while improved:
            improved = False

            for window_size in self.polish_window_sizes:
                if window_size > len(current.scheduled_programs):
                    continue

                for start_index in range(0, len(current.scheduled_programs) - window_size + 1):
                    candidate = self._repair_window(
                        solution=current,
                        start_index=start_index,
                        end_index=start_index + window_size,
                        guide=guide,
                    )

                    if candidate.total_score > current.total_score:
                        current = candidate.clone()
                        improved = True
                        break

                if improved:
                    break

        return current

    def _find_weakest_program_index(self, solution: CandidateSolution) -> int:
        weakest_index = 0
        weakest_value = float("inf")
        programs = solution.scheduled_programs

        for index, segment in enumerate(programs):
            value = float(segment.fitness)

            if index > 0:
                previous = programs[index - 1]

                if previous.channel_id != segment.channel_id:
                    value -= self.context.switch_penalty / 2

                if previous.genre == segment.genre:
                    value -= 1.5

            if index + 1 < len(programs):
                next_segment = programs[index + 1]

                if next_segment.channel_id != segment.channel_id:
                    value -= self.context.switch_penalty / 2

                if next_segment.genre == segment.genre:
                    value -= 1.5

            if value < weakest_value:
                weakest_value = value
                weakest_index = index

        return weakest_index

    @staticmethod
    def _window_around(center: int, size: int, total: int) -> tuple[int, int]:
        start = max(0, center - size // 2)
        end = min(total, start + size)

        if end - start < size:
            start = max(0, end - size)

        return start, end

    def _repair_window(
        self,
        solution: CandidateSolution,
        start_index: int,
        end_index: int,
        guide: Optional[CandidateSolution],
    ) -> CandidateSolution:
        prefix = solution.scheduled_programs[:start_index]
        suffix = solution.scheduled_programs[end_index:]

        left_time = prefix[-1].end if prefix else self.context.opening_time
        right_time = suffix[0].start if suffix else self.context.closing_time

        if left_time > right_time:
            return solution

        used_ids = {item.unique_program_id for item in prefix + suffix}
        guide_signatures = self._guide_signatures(guide)

        candidates = self._window_candidates(
            left_time=left_time,
            right_time=right_time,
            used_ids=used_ids,
            guide_signatures=guide_signatures,
        )

        previous_channel, previous_genre, previous_streak = self._left_context(prefix)

        beam = [
            {
                "score": 0,
                "end": left_time,
                "channel": previous_channel,
                "genre": previous_genre,
                "streak": previous_streak,
                "sequence": [],
                "inside_ids": set(),
            }
        ]

        best_sequence = []
        best_score = float("-inf")
        max_depth = self._max_depth(left_time, right_time)

        for _ in range(max_depth):
            next_beam = []

            for state in beam:
                terminal_score = self._score_connection_to_suffix(state, suffix)

                if terminal_score is not None and terminal_score > best_score:
                    best_score = terminal_score
                    best_sequence = state["sequence"]

                for item in candidates:
                    if not self._can_append(item, state):
                        continue

                    new_state = self._append_item(
                        state=state,
                        item=item,
                        guide_signatures=guide_signatures,
                    )

                    next_beam.append(new_state)

            if not next_beam:
                break

            next_beam.sort(key=lambda item: item["score"], reverse=True)
            beam = next_beam[: self.window_beam_width]

        merged = prefix + best_sequence + suffix

        repaired = self.context.solution_from_segments(
            merged,
            source="intelligent_ils_repair",
        )

        is_valid, _ = self.context.validate_schedule(repaired.scheduled_programs)

        if is_valid:
            return repaired

        return solution

    def _window_candidates(
        self,
        left_time: int,
        right_time: int,
        used_ids: set,
        guide_signatures: set,
    ) -> list[CandidateSegment]:
        candidates = []

        for item in self.catalog:
            if item.unique_program_id in used_ids:
                continue

            if item.start < left_time:
                continue

            if item.end > right_time:
                continue

            candidates.append(item)

        candidates.sort(
            key=lambda item: (
                item.signature() in guide_signatures,
                item.fitness,
                item.density,
            ),
            reverse=True,
        )

        return candidates[: self.window_candidate_limit]

    def _guide_signatures(self, guide: Optional[CandidateSolution]) -> set:
        if guide is None:
            return set()

        return {item.signature() for item in guide.scheduled_programs}

    def _left_context(
        self,
        prefix: list[CandidateSegment],
    ) -> tuple[Optional[int], str, int]:
        if not prefix:
            return None, "", 0

        last = prefix[-1]
        streak = 0

        for item in reversed(prefix):
            if item.genre == last.genre:
                streak += 1
            else:
                break

        return last.channel_id, last.genre, streak

    def _max_depth(self, left_time: int, right_time: int) -> int:
        duration = max(1, right_time - left_time)
        min_duration = max(1, self.context.min_duration)

        return max(1, duration // min_duration + 1)

    def _score_connection_to_suffix(
        self,
        state: dict,
        suffix: list[CandidateSegment],
    ):
        score = state["score"]

        if not suffix:
            return score

        next_item = suffix[0]

        if state["genre"] == next_item.genre:
            if state["streak"] + 1 > self.context.max_consecutive_genre:
                return None

        if state["channel"] is not None and state["channel"] != next_item.channel_id:
            score -= self.context.switch_penalty

        return score

    def _can_append(self, item: CandidateSegment, state: dict) -> bool:
        if item.unique_program_id in state["inside_ids"]:
            return False

        if item.start < state["end"]:
            return False

        if item.genre == state["genre"]:
            new_streak = state["streak"] + 1
        else:
            new_streak = 1

        if new_streak > self.context.max_consecutive_genre:
            return False

        return True

    def _append_item(
        self,
        state: dict,
        item: CandidateSegment,
        guide_signatures: set,
    ) -> dict:
        added_score = item.fitness

        if state["channel"] is not None and state["channel"] != item.channel_id:
            added_score -= self.context.switch_penalty

        if item.signature() in guide_signatures:
            added_score += 6

        if item.genre == state["genre"]:
            new_streak = state["streak"] + 1
        else:
            new_streak = 1

        inside_ids = set(state["inside_ids"])
        inside_ids.add(item.unique_program_id)

        return {
            "score": state["score"] + added_score,
            "end": item.end,
            "channel": item.channel_id,
            "genre": item.genre,
            "streak": new_streak,
            "sequence": state["sequence"] + [item],
            "inside_ids": inside_ids,
        }

    def _accept_worse_solution(
        self,
        candidate: CandidateSolution,
        current: CandidateSolution,
        stagnation: int,
    ) -> bool:
        loss = current.total_score - candidate.total_score
        tolerance = self.context.switch_penalty + stagnation * 2

        if loss <= tolerance and self.random.random() < 0.25:
            return True

        return False
