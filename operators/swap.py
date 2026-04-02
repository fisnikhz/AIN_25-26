from copy import deepcopy

from models.instance.instance_data import InstanceData
from models.solution.scheduled_program import ScheduledProgram
from models.solution.solution import Solution


def swap(
    instance: InstanceData,
    state: Solution,
    program_a: ScheduledProgram,
    program_b: ScheduledProgram,
) -> Solution:

    copy = deepcopy(state)

    idx_a = None
    idx_b = None
    for i, p in enumerate(copy.selected.scheduled_programs):
        if p.program_id == program_a.program_id and p.channel_id == program_a.channel_id:
            idx_a = i
        elif p.program_id == program_b.program_id and p.channel_id == program_b.channel_id:
            idx_b = i

    if idx_a is None or idx_b is None:
        return state

    a = copy.selected.scheduled_programs[idx_a]
    b = copy.selected.scheduled_programs[idx_b]

    a.start, b.start = b.start, a.start
    a.end, b.end = b.end, a.end

    copy.selected.scheduled_programs = _sorted_schedule(copy.selected.scheduled_programs)

    if not _is_feasible_swap(copy.selected.scheduled_programs, instance):
        return state

    copy._fitness = None
    return copy


def swap_two(
    instance: InstanceData,
    state: Solution,
    program_a: ScheduledProgram,
    program_b: ScheduledProgram,
) -> Solution:
    return swap(instance, state, program_a, program_b)


def _sorted_schedule(schedule: list[ScheduledProgram]) -> list[ScheduledProgram]:
    return sorted(
        schedule,
        key=lambda program: (program.start, program.end, program.channel_id, program.program_id),
    )


def _is_feasible_swap(schedule: list[ScheduledProgram], instance: InstanceData) -> bool:
    if not schedule:
        return True

    lookup = _instance_program_lookup(instance)

    prev_end = None
    for sp in schedule:
        if sp.start < instance.opening_time or sp.end > instance.closing_time:
            return False
        if sp.start >= sp.end:
            return False
        if prev_end is not None and prev_end > sp.start:
            return False
        prev_end = sp.end

        if not _respects_priority_blocks(sp.start, sp.end, sp.channel_id, instance):
            return False

        inst_p = lookup.get((sp.channel_id, sp.program_id))
        if inst_p is None:
            return False
        if sp.start < inst_p.start or sp.end > inst_p.end:
            return False
        if (sp.end - sp.start) < instance.min_duration:
            return False

    if not _respects_genre_limit(schedule, instance, lookup):
        return False

    return True


def _respects_priority_blocks(start: int, end: int, channel_id: int, instance: InstanceData) -> bool:
    for block in instance.priority_blocks:
        overlaps = min(end, block.end) > max(start, block.start)
        if overlaps and channel_id not in block.allowed_channels:
            return False
    return True


def _instance_program_lookup(instance: InstanceData) -> dict[tuple[int, str], object]:
    lookup = {}
    for channel in instance.channels:
        for program in channel.programs:
            lookup[(channel.channel_id, program.program_id)] = program
    return lookup


def _respects_genre_limit(
    schedule: list[ScheduledProgram],
    instance: InstanceData,
    lookup: dict[tuple[int, str], object],
) -> bool:
    consecutive = 0
    last_genre = None

    for scheduled_program in schedule:
        inst_p = lookup.get((scheduled_program.channel_id, scheduled_program.program_id))
        if inst_p is None:
            return False
        genre = inst_p.genre
        if genre == last_genre:
            consecutive += 1
        else:
            last_genre = genre
            consecutive = 1

        if consecutive > instance.max_consecutive_genre:
            return False

    return True

