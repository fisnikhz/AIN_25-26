from copy import deepcopy
from typing import List, Optional, Tuple

from models.instance.instance_data import InstanceData
from models.solution.scheduled_program import ScheduledProgram
from models.solution.solution import Solution


def insert_best(solution: Solution, instance: InstanceData) -> Solution:
    """
    Insert inteligjent, por bazik:
    - gjen gaps globale në timeline;
    - shikon programet e pa zgjedhura;
    - provon disa dritare të vlefshme brenda programit origjinal;
    - pranon vetëm kandidat valid;
    - kthen kandidatin me fitness më të mirë.
    """

    state = deepcopy(solution)

    if not state.unselected_ids:
        return state

    gaps = _find_global_gaps(state.selected.scheduled_programs, instance)

    if not gaps:
        return state

    best_solution = state
    best_fitness = state.fitness

    unselected_ids = set(state.unselected_ids)

    for program, channel_id in _all_unselected_programs(instance, unselected_ids):
        for gap_start, gap_end in gaps:
            windows = _candidate_windows(
                program=program,
                gap_start=gap_start,
                gap_end=gap_end,
                instance=instance,
            )

            for start, end in windows:
                candidate = deepcopy(state)

                new_sp = ScheduledProgram(
                    program_id=program.program_id,
                    channel_id=channel_id,
                    start=start,
                    end=end,
                )

                candidate.selected.scheduled_programs.append(new_sp)
                candidate.selected.scheduled_programs = _sorted_schedule(
                    candidate.selected.scheduled_programs
                )

                if program.program_id in candidate.unselected_ids:
                    candidate.unselected_ids.remove(program.program_id)

                candidate._fitness = None

                if not _is_feasible_schedule(candidate.selected.scheduled_programs, instance):
                    continue

                if candidate.fitness > best_fitness:
                    best_solution = candidate
                    best_fitness = candidate.fitness

    return best_solution


def insert(solution: Solution, instance: InstanceData) -> Solution:
    return insert_best(solution, instance)


def insertion_stats(solution: Solution, instance: InstanceData):
    gaps = _find_global_gaps(solution.selected.scheduled_programs, instance)

    return {
        "gaps": len(gaps),
        "unselected": len(solution.unselected_ids),
        "placeable_any": 1 if gaps and solution.unselected_ids else 0,
    }


def _find_global_gaps(
    schedule: List[ScheduledProgram],
    instance: InstanceData,
) -> List[Tuple[int, int]]:
    ordered = _sorted_schedule(schedule)
    gaps = []

    cursor = instance.opening_time

    for sp in ordered:
        if sp.start > cursor:
            gaps.append((cursor, sp.start))
        cursor = max(cursor, sp.end)

    if cursor < instance.closing_time:
        gaps.append((cursor, instance.closing_time))

    return [
        (start, end)
        for start, end in gaps
        if end > start
    ]


def _all_unselected_programs(instance: InstanceData, unselected_ids: set[str]):
    programs = []

    for channel in instance.channels:
        for program in channel.programs:
            if program.program_id in unselected_ids:
                programs.append((program, channel.channel_id))

    programs.sort(key=lambda item: item[0].score, reverse=True)

    return programs


def _candidate_windows(program, gap_start: int, gap_end: int, instance: InstanceData):
    windows = set()

    left = max(gap_start, program.start, instance.opening_time)
    right = min(gap_end, program.end, instance.closing_time)

    full_duration = program.end - program.start

    if full_duration < instance.min_duration:
        if gap_start <= program.start and program.end <= gap_end:
            windows.add((program.start, program.end))
        return list(windows)

    if right - left < instance.min_duration:
        return []

    windows.add((left, right))
    windows.add((left, left + instance.min_duration))
    windows.add((right - instance.min_duration, right))

    if gap_start <= program.start and program.end <= gap_end:
        windows.add((program.start, program.end))

    clean = []

    for start, end in windows:
        if start >= program.start and end <= program.end and start < end:
            clean.append((start, end))

    clean.sort(key=lambda x: (x[0], x[1]))

    return clean


def _is_feasible_schedule(
    schedule: List[ScheduledProgram],
    instance: InstanceData,
) -> bool:
    ordered = _sorted_schedule(schedule)
    lookup = _program_lookup(instance)

    previous = None
    seen = set()
    last_genre = None
    genre_count = 0

    for sp in ordered:
        original = lookup.get((sp.channel_id, sp.program_id))

        if original is None:
            return False

        unique_key = (sp.channel_id, sp.program_id)
        if unique_key in seen:
            return False
        seen.add(unique_key)

        if sp.start < instance.opening_time or sp.end > instance.closing_time:
            return False

        if sp.start < original.start or sp.end > original.end:
            return False

        if sp.start >= sp.end:
            return False

        full_duration = original.end - original.start
        duration = sp.end - sp.start

        if full_duration < instance.min_duration:
            if sp.start != original.start or sp.end != original.end:
                return False
        elif duration < instance.min_duration:
            return False

        for block in instance.priority_blocks:
            overlaps = min(sp.end, block.end) > max(sp.start, block.start)
            if overlaps and sp.channel_id not in block.allowed_channels:
                return False

        if previous is not None and previous.end > sp.start:
            return False

        genre = original.genre

        if genre == last_genre:
            genre_count += 1
        else:
            last_genre = genre
            genre_count = 1

        if genre_count > instance.max_consecutive_genre:
            return False

        previous = sp

    return True


def _program_lookup(instance: InstanceData):
    lookup = {}

    for channel in instance.channels:
        for program in channel.programs:
            lookup[(channel.channel_id, program.program_id)] = program

    return lookup


def _sorted_schedule(schedule: List[ScheduledProgram]) -> List[ScheduledProgram]:
    return sorted(
        schedule,
        key=lambda p: (p.start, p.end, p.channel_id, p.program_id),
    )