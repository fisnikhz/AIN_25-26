import random
from copy import deepcopy

from models.instance.instance_data import InstanceData
from models.solution.scheduled_program import ScheduledProgram
from models.solution.solution import Solution


def replace(solution: Solution, instance: InstanceData) -> Solution:
    copy = deepcopy(solution)

    if len(copy.selected) == 0 or not copy.unselected_ids:
        return copy

    ordered = _sorted_schedule(copy.selected.scheduled_programs)
    removable_programs = ordered[:]
    random.shuffle(removable_programs)

    for old_program in removable_programs:
        old_index = _find_program_index(ordered, old_program)
        if old_index is None:
            continue

        gap_start = instance.opening_time if old_index == 0 else ordered[old_index - 1].end
        gap_end = instance.closing_time if old_index == len(ordered) - 1 else ordered[old_index + 1].start

        candidates = _valid_replacements(
            gap_start=gap_start,
            gap_end=gap_end,
            unselected_ids=set(copy.unselected_ids),
            instance=instance,
        )

        if not candidates:
            continue

        new_program, new_channel_id = random.choice(candidates)
        ordered[old_index] = ScheduledProgram(
            program_id=new_program.program_id,
            channel_id=new_channel_id,
            start=new_program.start,
            end=new_program.end,
        )

        if not _respects_genre_limit(ordered, instance):
            ordered[old_index] = old_program
            continue

        copy.selected.scheduled_programs = ordered
        if old_program.program_id not in copy.unselected_ids:
            copy.unselected_ids.append(old_program.program_id)
        if new_program.program_id in copy.unselected_ids:
            copy.unselected_ids.remove(new_program.program_id)
        copy._fitness = None
        return copy

    return copy


def _valid_replacements(gap_start: int,
                        gap_end: int,
                        unselected_ids: set[str],
                        instance: InstanceData) -> list[tuple]:
    candidates = []

    for channel in instance.channels:
        for program in channel.programs:
            if program.program_id not in unselected_ids:
                continue

            if not _fits_gap(program.start, program.end, gap_start, gap_end):
                continue

            if not _has_valid_program_duration(program):
                continue

            if not _respects_priority_blocks(program.start, program.end, channel.channel_id, instance):
                continue

            candidates.append((program, channel.channel_id))

    return candidates


def _fits_gap(start: int, end: int, gap_start: int, gap_end: int) -> bool:
    return start >= gap_start and end <= gap_end and start < end


def _has_valid_program_duration(program) -> bool:
    return program.end > program.start


def _respects_priority_blocks(start: int,
                              end: int,
                              channel_id: int,
                              instance: InstanceData) -> bool:
    for block in instance.priority_blocks:
        overlaps = min(end, block.end) > max(start, block.start)
        if overlaps and channel_id not in block.allowed_channels:
            return False
    return True


def _respects_genre_limit(schedule: list[ScheduledProgram], instance: InstanceData) -> bool:
    lookup = _program_lookup(instance)
    consecutive = 0
    last_genre = None

    for scheduled_program in schedule:
        genre = lookup[(scheduled_program.channel_id, scheduled_program.program_id)].genre
        if genre == last_genre:
            consecutive += 1
        else:
            last_genre = genre
            consecutive = 1

        if consecutive > instance.max_consecutive_genre:
            return False

    return True


def _program_lookup(instance: InstanceData) -> dict[tuple[int, str], object]:
    lookup = {}
    for channel in instance.channels:
        for program in channel.programs:
            lookup[(channel.channel_id, program.program_id)] = program
    return lookup


def _sorted_schedule(schedule: list[ScheduledProgram]) -> list[ScheduledProgram]:
    return sorted(
        schedule,
        key=lambda program: (program.start, program.end, program.channel_id, program.program_id),
    )


def _find_program_index(schedule: list[ScheduledProgram], target: ScheduledProgram) -> int | None:
    for index, program in enumerate(schedule):
        if program.program_id == target.program_id and program.channel_id == target.channel_id:
            return index
    return None
