from copy import deepcopy

from models.instance.instance_data import InstanceData
from models.solution.scheduled_program import ScheduledProgram
from models.solution.solution import Solution
from utils.schedule_feasibility import (
    build_program_lookup,
    is_schedule_feasible,
    sort_schedule,
)


def swap(
    instance: InstanceData,
    state: Solution,
    program_a: ScheduledProgram,
    program_b: ScheduledProgram,
) -> Solution:
    copy_state = deepcopy(state)

    idx_a = None
    idx_b = None
    for i, scheduled_program in enumerate(copy_state.selected.scheduled_programs):
        if (
            scheduled_program.program_id == program_a.program_id
            and scheduled_program.channel_id == program_a.channel_id
        ):
            idx_a = i
        elif (
            scheduled_program.program_id == program_b.program_id
            and scheduled_program.channel_id == program_b.channel_id
        ):
            idx_b = i

    if idx_a is None or idx_b is None:
        return state

    program_left = copy_state.selected.scheduled_programs[idx_a]
    program_right = copy_state.selected.scheduled_programs[idx_b]

    program_left.start, program_right.start = program_right.start, program_left.start
    program_left.end, program_right.end = program_right.end, program_left.end

    copy_state.selected.scheduled_programs = sort_schedule(copy_state.selected.scheduled_programs)

    if not is_schedule_feasible(copy_state.selected.scheduled_programs, instance):
        return state

    copy_state._fitness = None
    return copy_state


def swap_heuristic(instance: InstanceData, state: Solution) -> Solution:
    ordered = sort_schedule(list(state.selected.scheduled_programs))
    if len(ordered) < 2:
        return state

    switch_points = _find_switch_points(ordered)
    if not switch_points:
        return state

    lookup = build_program_lookup(instance)
    ranked_candidates = []

    for left_index in switch_points:
        right_index = left_index + 1
        if right_index >= len(ordered):
            continue

        before_switches = _boundary_switch_count(ordered, left_index)
        after_switches = _boundary_switch_count_after_swap(ordered, left_index)
        switch_gain = before_switches - after_switches

        left_program = ordered[left_index]
        right_program = ordered[right_index]
        time_pref_gain = (
            _scheduled_time_pref_bonus(
                right_program,
                left_program.start,
                left_program.end,
                instance,
                lookup,
            )
            + _scheduled_time_pref_bonus(
                left_program,
                right_program.start,
                right_program.end,
                instance,
                lookup,
            )
            - _scheduled_time_pref_bonus(
                left_program,
                left_program.start,
                left_program.end,
                instance,
                lookup,
            )
            - _scheduled_time_pref_bonus(
                right_program,
                right_program.start,
                right_program.end,
                instance,
                lookup,
            )
        )

        ranked_candidates.append((switch_gain, time_pref_gain, left_program, right_program))

    ranked_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)

    for _, _, left_program, right_program in ranked_candidates[:3]:
        neighbor = swap(instance, state, left_program, right_program)
        if neighbor is not state:
            return neighbor

    return state


def swap_two(
    instance: InstanceData,
    state: Solution,
    program_a: ScheduledProgram,
    program_b: ScheduledProgram,
) -> Solution:
    return swap(instance, state, program_a, program_b)


def _find_switch_points(schedule: list[ScheduledProgram]) -> list[int]:
    return [
        i
        for i in range(len(schedule) - 1)
        if schedule[i].channel_id != schedule[i + 1].channel_id
    ]


def _boundary_switch_count(schedule: list[ScheduledProgram], left_index: int) -> int:
    boundaries = 0
    for boundary_index in (left_index - 1, left_index, left_index + 1):
        if 0 <= boundary_index < len(schedule) - 1:
            if schedule[boundary_index].channel_id != schedule[boundary_index + 1].channel_id:
                boundaries += 1
    return boundaries


def _boundary_switch_count_after_swap(schedule: list[ScheduledProgram], left_index: int) -> int:
    swapped = list(schedule)
    swapped[left_index], swapped[left_index + 1] = swapped[left_index + 1], swapped[left_index]
    return _boundary_switch_count(swapped, left_index)


def _scheduled_time_pref_bonus(
    scheduled_program: ScheduledProgram,
    start: int,
    end: int,
    instance: InstanceData,
    lookup: dict[tuple[int, str], object],
) -> float:
    instance_program = lookup.get((scheduled_program.channel_id, scheduled_program.program_id))
    if instance_program is None:
        return 0.0

    bonus = 0.0
    for preference in instance.time_preferences:
        if instance_program.genre != preference.preferred_genre:
            continue
        overlap = min(end, preference.end) - max(start, preference.start)
        if overlap >= instance.min_duration:
            bonus += preference.bonus
    return bonus
