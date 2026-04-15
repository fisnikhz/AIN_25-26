from models.instance.instance_data import InstanceData
from models.solution.scheduled_program import ScheduledProgram


def build_program_lookup(instance: InstanceData) -> dict[tuple[int, str], object]:
    lookup = {}
    for channel in instance.channels:
        for program in channel.programs:
            lookup[(channel.channel_id, program.program_id)] = program
    return lookup


def sort_schedule(schedule: list[ScheduledProgram]) -> list[ScheduledProgram]:
    return sorted(
        schedule,
        key=lambda program: (program.start, program.end, program.channel_id, program.program_id),
    )


def respects_priority_blocks(start: int, end: int, channel_id: int, instance: InstanceData) -> bool:
    for block in instance.priority_blocks:
        overlaps = min(end, block.end) > max(start, block.start)
        if overlaps and channel_id not in block.allowed_channels:
            return False
    return True


def respects_genre_limit(
    schedule: list[ScheduledProgram],
    instance: InstanceData,
    lookup: dict[tuple[int, str], object] | None = None,
) -> bool:
    lookup = lookup or build_program_lookup(instance)

    consecutive = 0
    last_genre = None

    for scheduled_program in schedule:
        inst_program = lookup.get((scheduled_program.channel_id, scheduled_program.program_id))
        if inst_program is None:
            return False

        genre = inst_program.genre
        if genre == last_genre:
            consecutive += 1
        else:
            last_genre = genre
            consecutive = 1

        if consecutive > instance.max_consecutive_genre:
            return False

    return True


def is_schedule_feasible(
    schedule: list[ScheduledProgram],
    instance: InstanceData,
    lookup: dict[tuple[int, str], object] | None = None,
) -> bool:
    if not schedule:
        return True

    ordered = sort_schedule(schedule)
    lookup = lookup or build_program_lookup(instance)

    prev_end = None
    for sp in ordered:
        if sp.start < instance.opening_time or sp.end > instance.closing_time:
            return False
        if sp.start >= sp.end:
            return False
        if prev_end is not None and prev_end > sp.start:
            return False
        prev_end = sp.end

        if not respects_priority_blocks(sp.start, sp.end, sp.channel_id, instance):
            return False

        inst_program = lookup.get((sp.channel_id, sp.program_id))
        if inst_program is None:
            return False
        if sp.start < inst_program.start or sp.end > inst_program.end:
            return False
        if (sp.end - sp.start) < instance.min_duration:
            return False

    return respects_genre_limit(ordered, instance, lookup)
