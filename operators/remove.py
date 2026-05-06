# operators/remove.py

import random
from copy import deepcopy

from models.instance.instance_data import InstanceData
from models.solution.scheduled_program import ScheduledProgram
from models.solution.solution import Solution


def remove(solution: Solution, program: ScheduledProgram) -> Solution:
    """
    Normal remove operator.
    Algoritmi e zgjedh programin; ky funksion vetëm e largon.
    """
    state = deepcopy(solution)
    return _remove_program(state, program)


def remove_advanced(solution: Solution, instance: InstanceData) -> Solution:
    """
    Advanced remove operator.
    Ky funksion vetë e zgjedh programin më të dobët për largim.
    """
    state = deepcopy(solution)

    if not state.selected.scheduled_programs:
        return state

    lookup = _program_lookup(instance)
    ordered = _sorted_schedule(state.selected.scheduled_programs)

    worst_program = None
    worst_value = float("inf")

    for index, scheduled_program in enumerate(ordered):
        value = _removal_value(
            schedule=ordered,
            index=index,
            scheduled_program=scheduled_program,
            instance=instance,
            lookup=lookup,
        )

        if value < worst_value:
            worst_value = value
            worst_program = scheduled_program

    if worst_program is None:
        return state

    return _remove_program(state, worst_program)


def _remove_program(state: Solution, program_to_remove: ScheduledProgram) -> Solution:
    new_schedule = []
    removed = False

    for scheduled_program in state.selected.scheduled_programs:
        same_program = (
            scheduled_program.program_id == program_to_remove.program_id
            and scheduled_program.channel_id == program_to_remove.channel_id
        )

        if same_program and not removed:
            removed = True
            continue

        new_schedule.append(scheduled_program)

    if not removed:
        return state

    state.selected.scheduled_programs = _sorted_schedule(new_schedule)

    if program_to_remove.program_id not in state.unselected_ids:
        state.unselected_ids.append(program_to_remove.program_id)

    state._fitness = None
    return state


def _removal_value(
    schedule: list[ScheduledProgram],
    index: int,
    scheduled_program: ScheduledProgram,
    instance: InstanceData,
    lookup: dict[tuple[int, str], object],
) -> float:
    instance_program = lookup.get(
        (scheduled_program.channel_id, scheduled_program.program_id)
    )

    if instance_program is None:
        return 0.0

    scheduled_duration = scheduled_program.end - scheduled_program.start
    original_duration = max(1, instance_program.end - instance_program.start)

    duration_ratio = scheduled_duration / original_duration

    program_score = instance_program.score * duration_ratio
    bonus = _time_preference_bonus(scheduled_program, instance_program.genre, instance)
    switch_effect = _switch_effect(schedule, index, instance)
    created_gap = _created_gap(schedule, index, instance)

    gap_reward = created_gap * 0.05

    value = program_score + bonus - switch_effect - gap_reward

    return max(0.0, value)


def _switch_effect(
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


def _created_gap(
    schedule: list[ScheduledProgram],
    index: int,
    instance: InstanceData,
) -> int:
    left_end = instance.opening_time if index == 0 else schedule[index - 1].end
    right_start = instance.closing_time if index == len(schedule) - 1 else schedule[index + 1].start

    return max(0, right_start - left_end)


def _time_preference_bonus(
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


def _program_lookup(instance: InstanceData) -> dict[tuple[int, str], object]:
    lookup = {}

    for channel in instance.channels:
        for program in channel.programs:
            lookup[(channel.channel_id, program.program_id)] = program

    return lookup


def _sorted_schedule(schedule: list[ScheduledProgram]) -> list[ScheduledProgram]:
    return sorted(
        schedule,
        key=lambda program: (
            program.start,
            program.end,
            program.channel_id,
            program.program_id,
        ),
    )