from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

from io_utils.initial_solution_parser import SolutionParser
from io_utils.instance_parser import InstanceParser
from models.solution.scheduled_program import ScheduledProgram


@dataclass(frozen=True)
class CandidateSegment:
    program_id: str
    channel_id: int
    start: int
    end: int
    unique_program_id: int | str
    genre: str
    score: int
    bonus: int
    cut_penalty: int
    original_start: int
    original_end: int
    fitness: int
    source: str = "generated"

    @property
    def duration(self) -> int:
        return self.end - self.start

    @property
    def density(self) -> float:
        duration = self.duration
        if duration <= 0:
            return float("-inf")
        return self.fitness / duration

    def signature(self) -> tuple[int | str, int, int]:
        return self.unique_program_id, self.start, self.end

    def to_output_dict(self) -> dict[str, int | str]:
        return {
            "program_id": self.program_id,
            "channel_id": self.channel_id,
            "start": self.start,
            "end": self.end,
        }

    def to_scheduled_program(self) -> ScheduledProgram:
        return ScheduledProgram(
            program_id=self.program_id,
            channel_id=self.channel_id,
            start=self.start,
            end=self.end,
        )


@dataclass
class CandidateSolution:
    scheduled_programs: list[CandidateSegment] = field(default_factory=list)
    total_score: int = 0
    source: str = "unknown"
    metadata: dict[str, object] = field(default_factory=dict)

    def signature(self) -> tuple[tuple[int | str, int, int], ...]:
        ordered = sorted(
            self.scheduled_programs,
            key=lambda item: (item.start, item.end, item.channel_id, str(item.program_id)),
        )
        return tuple(item.signature() for item in ordered)

    def clone(self) -> "CandidateSolution":
        return CandidateSolution(
            scheduled_programs=list(self.scheduled_programs),
            total_score=self.total_score,
            source=self.source,
            metadata=dict(self.metadata),
        )


class InstanceContext:
    def __init__(self, instance):
        self.instance = instance
        self.opening_time = instance.opening_time
        self.closing_time = instance.closing_time
        self.min_duration = instance.min_duration
        self.max_consecutive_genre = instance.max_consecutive_genre
        self.switch_penalty = instance.switch_penalty
        self.termination_penalty = instance.termination_penalty
        self.priority_blocks = sorted(
            [
                (block.start, block.end, set(block.allowed_channels))
                for block in getattr(instance, "priority_blocks", [])
            ],
            key=lambda item: (item[0], item[1]),
        )
        self.time_preferences = list(getattr(instance, "time_preferences", []))

        self.program_lookup: dict[tuple[int, str], object] = {}
        self.unique_program_lookup: dict[int | str, tuple[int, object]] = {}
        self.channels_by_id: dict[int, object] = {}
        densities: list[float] = []

        for channel in instance.channels:
            self.channels_by_id[channel.channel_id] = channel
            for program in channel.programs:
                self.program_lookup[(channel.channel_id, program.program_id)] = program
                self.unique_program_lookup[program.unique_id] = (channel.channel_id, program)
                duration = max(1, program.end - program.start)
                densities.append(program.score / duration)

        densities.sort(reverse=True)
        head = max(1, len(densities) // 10) if densities else 1
        self.optimistic_density = sum(densities[:head]) / head if densities else 1.0

    @staticmethod
    def interval_overlap_len(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
        return max(0, min(a_end, b_end) - max(a_start, b_start))

    def channel_allowed(self, channel_id: int, start: int, end: int) -> bool:
        for block_start, block_end, allowed_channels in self.priority_blocks:
            if block_end <= start:
                continue
            if block_start >= end:
                break
            if channel_id not in allowed_channels:
                return False
        return True

    def compute_bonus(self, genre: str, start: int, end: int) -> int:
        total = 0
        for pref in self.time_preferences:
            if genre != pref.preferred_genre:
                continue
            overlap = self.interval_overlap_len(start, end, pref.start, pref.end)
            if overlap >= self.min_duration:
                total += pref.bonus
        return total

    def create_segment(self, channel_id: int, program, start: int, end: int, source: str) -> CandidateSegment:
        bonus = self.compute_bonus(program.genre, start, end)
        cut_penalty = 0
        if start > program.start:
            cut_penalty += self.termination_penalty
        if end < program.end:
            cut_penalty += self.termination_penalty

        fitness = int(program.score + bonus - cut_penalty)

        return CandidateSegment(
            program_id=program.program_id,
            channel_id=channel_id,
            start=start,
            end=end,
            unique_program_id=program.unique_id,
            genre=program.genre,
            score=program.score,
            bonus=bonus,
            cut_penalty=cut_penalty,
            original_start=program.start,
            original_end=program.end,
            fitness=fitness,
            source=source,
        )

    def enrich_segment(self, item, source: str = "external") -> CandidateSegment:
        program = self.program_lookup[(item.channel_id, item.program_id)]
        return self.create_segment(
            channel_id=item.channel_id,
            program=program,
            start=item.start,
            end=item.end,
            source=source,
        )

    def evaluate_segments(self, scheduled_programs: Sequence[CandidateSegment]) -> int:
        if not scheduled_programs:
            return 0

        total = 0
        previous_channel = None

        for item in scheduled_programs:
            total += item.fitness
            if previous_channel is not None and item.channel_id != previous_channel:
                total -= self.switch_penalty
            previous_channel = item.channel_id

        return int(total)

    def solution_from_segments(
        self,
        segments: Iterable[CandidateSegment],
        source: str,
        metadata: Optional[dict[str, object]] = None,
    ) -> CandidateSolution:
        ordered = sorted(
            list(segments),
            key=lambda item: (item.start, item.end, item.channel_id, str(item.program_id)),
        )
        return CandidateSolution(
            scheduled_programs=ordered,
            total_score=self.evaluate_segments(ordered),
            source=source,
            metadata=metadata or {},
        )

    def is_valid_segment(self, item: CandidateSegment) -> tuple[bool, str]:
        program = self.program_lookup.get((item.channel_id, item.program_id))
        if program is None:
            return False, f"program {item.program_id} on channel {item.channel_id} does not exist"

        if item.start < self.opening_time or item.end > self.closing_time:
            return False, f"segment {item.signature()} is outside opening/closing hours"

        if item.start < program.start or item.end > program.end or item.start >= item.end:
            return False, f"segment {item.signature()} is outside the original program bounds"

        full_duration = program.end - program.start
        duration = item.end - item.start
        if full_duration < self.min_duration:
            if item.start != program.start or item.end != program.end:
                return False, f"short program {item.signature()} must be watched fully"
        elif duration < self.min_duration:
            return False, f"segment {item.signature()} is shorter than min_duration"

        if not self.channel_allowed(item.channel_id, item.start, item.end):
            return False, f"segment {item.signature()} violates a priority block"

        return True, ""

    def validate_schedule(self, scheduled_programs: Sequence[CandidateSegment]) -> tuple[bool, str]:
        previous = None
        seen_unique_ids: set[int | str] = set()
        previous_genre = None
        genre_streak = 0

        for item in scheduled_programs:
            valid, reason = self.is_valid_segment(item)
            if not valid:
                return False, reason

            if item.unique_program_id in seen_unique_ids:
                return False, f"program {item.unique_program_id} is scheduled more than once"
            seen_unique_ids.add(item.unique_program_id)

            if previous is not None and previous.end > item.start:
                return False, f"segments {previous.signature()} and {item.signature()} overlap"

            if previous_genre == item.genre:
                genre_streak += 1
            else:
                previous_genre = item.genre
                genre_streak = 1

            if genre_streak > self.max_consecutive_genre:
                return False, f"genre streak for {item.genre} exceeds R={self.max_consecutive_genre}"

            previous = item

        return True, ""


def load_instance(instance_path: str | Path):
    return InstanceParser(str(instance_path)).parse()


def load_candidate_solution(instance, solution_path: str | Path, source: str) -> CandidateSolution:
    context = InstanceContext(instance)
    raw_schedule = SolutionParser(solution_path).parse()

    segments = [
        context.enrich_segment(scheduled_program, source)
        for scheduled_program in raw_schedule.scheduled_programs
    ]

    candidate = context.solution_from_segments(
        segments,
        source=source,
        metadata={"solution_path": str(solution_path)},
    )

    is_valid, reason = context.validate_schedule(candidate.scheduled_programs)
    if not is_valid:
        raise ValueError(f"Seed solution from {solution_path} is invalid: {reason}")

    return candidate


def save_solution(solution: CandidateSolution, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "scheduled_programs": [item.to_output_dict() for item in solution.scheduled_programs]
    }
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=4)
    return path
