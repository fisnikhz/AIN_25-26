from copy import deepcopy
from enum import Enum, auto

import config.hill_climbing_config as config
from models.instance.instance_data import InstanceData
from models.solution.scheduled_program import ScheduledProgram
from models.solution.solution import Solution
from utils.schedule_feasibility import build_program_lookup, is_schedule_feasible, sort_schedule


class TargetBorder(Enum):
    left = auto()
    right = auto()


class Mode(Enum):
    shrink = auto()
    expand = auto()


def shift_borders_heuristic(instance: InstanceData, state: Solution) -> Solution:
    ordered = sort_schedule(list(state.selected.scheduled_programs))
    if not ordered:
        return state

    lookup = build_program_lookup(instance)
    current_fitness = state.fitness
    best_neighbor = state
    best_delta = 0.0
    best_priority = float("-inf")

    for program in ordered:
        for border in TargetBorder:
            candidate = _best_shift_move(instance, state, program, border, lookup, current_fitness)
            if candidate is None:
                continue

            neighbor, delta, priority = candidate
            if delta > best_delta or (delta == best_delta and priority > best_priority):
                best_neighbor = neighbor
                best_delta = delta
                best_priority = priority

    return best_neighbor


def shift_borders(
    instance: InstanceData,
    state: Solution,
    program: ScheduledProgram,
    mode: Mode,
    border: TargetBorder,
    shamt: int,
) -> Solution:
    copy_state = deepcopy(state)

    max_shift = _max_shift_distance(instance, copy_state, program, mode, border)
    if max_shift is None or max_shift <= 0:
        return state

    shift_amount = min(abs(shamt), abs(max_shift))
    if shift_amount <= 0:
        return state

    for i, scheduled_program in enumerate(copy_state.selected.scheduled_programs):
        if (
            scheduled_program.program_id == program.program_id
            and scheduled_program.channel_id == program.channel_id
        ):
            if mode == Mode.shrink:
                if border == TargetBorder.left:
                    copy_state.selected.scheduled_programs[i].start += shift_amount
                elif border == TargetBorder.right:
                    copy_state.selected.scheduled_programs[i].end -= shift_amount
            elif mode == Mode.expand:
                if border == TargetBorder.left:
                    copy_state.selected.scheduled_programs[i].start -= shift_amount
                elif border == TargetBorder.right:
                    copy_state.selected.scheduled_programs[i].end += shift_amount
            break

    copy_state.selected.scheduled_programs = sort_schedule(copy_state.selected.scheduled_programs)
    if not is_schedule_feasible(copy_state.selected.scheduled_programs, instance):
        return state

    copy_state._fitness = None
    return copy_state


def _best_shift_move(
    instance: InstanceData,
    state: Solution,
    program: ScheduledProgram,
    border: TargetBorder,
    lookup: dict[tuple[int, str], object],
    current_fitness: float,
):
    max_shift = _max_shift_distance(instance, state, program, Mode.expand, border)
    if max_shift is None or max_shift <= 0:
        return None

    original = lookup.get((program.channel_id, program.program_id))
    if original is None:
        return None

    best_neighbor = None
    best_delta = float("-inf")
    best_priority = float("-inf")

    for shamt in _candidate_expand_amounts(instance, program, original.genre, border, max_shift):
        neighbor = shift_borders(instance, state, program, Mode.expand, border, shamt)
        if neighbor is state:
            continue

        shifted_program = _find_program(neighbor.selected.scheduled_programs, program)
        if shifted_program is None:
            continue

        delta = neighbor.fitness - current_fitness
        priority = _shift_priority(program, shifted_program, original, instance)
        if delta > best_delta or (delta == best_delta and priority > best_priority):
            best_neighbor = neighbor
            best_delta = delta
            best_priority = priority

    if best_neighbor is None:
        return None

    return best_neighbor, best_delta, best_priority


def _candidate_expand_amounts(
    instance: InstanceData,
    program: ScheduledProgram,
    genre: str,
    border: TargetBorder,
    max_shift: int,
) -> list[int]:
    amounts = {max_shift, min(max_shift, config.MAX_SHIFT)}

    bonus_capture_amount = _bonus_capture_amount(instance, program, genre, border, max_shift)
    if bonus_capture_amount is not None:
        amounts.add(bonus_capture_amount)

    return sorted(amount for amount in amounts if amount > 0)


def _bonus_capture_amount(
    instance: InstanceData,
    program: ScheduledProgram,
    genre: str,
    border: TargetBorder,
    max_shift: int,
) -> int | None:
    best_amount = None

    for preference in instance.time_preferences:
        if preference.preferred_genre != genre:
            continue

        current_overlap = _compute_overlap(
            program.start,
            program.end,
            preference.start,
            preference.end,
        )
        if current_overlap >= instance.min_duration:
            continue

        for shamt in range(1, max_shift + 1):
            if border == TargetBorder.left:
                shifted_start = program.start - shamt
                shifted_end = program.end
            else:
                shifted_start = program.start
                shifted_end = program.end + shamt

            overlap = _compute_overlap(
                shifted_start,
                shifted_end,
                preference.start,
                preference.end,
            )
            if overlap >= instance.min_duration:
                if best_amount is None or shamt < best_amount:
                    best_amount = shamt
                break

    return best_amount


def _shift_priority(
    before: ScheduledProgram,
    after: ScheduledProgram,
    original,
    instance: InstanceData,
) -> float:
    timing_gain = 0.0

    if before.start > original.start and after.start == original.start:
        timing_gain += instance.termination_penalty
    if before.end < original.end and after.end == original.end:
        timing_gain += instance.termination_penalty

    bonus_gain = (
        _time_pref_bonus_for_window(original.genre, after.start, after.end, instance)
        - _time_pref_bonus_for_window(original.genre, before.start, before.end, instance)
    )

    recovered_duration = (after.end - after.start) - (before.end - before.start)
    return timing_gain + bonus_gain + (recovered_duration / max(1, instance.min_duration))


def _time_pref_bonus_for_window(genre: str, start: int, end: int, instance: InstanceData) -> float:
    bonus = 0.0
    for preference in instance.time_preferences:
        if preference.preferred_genre != genre:
            continue
        overlap = _compute_overlap(start, end, preference.start, preference.end)
        if overlap >= instance.min_duration:
            bonus += preference.bonus
    return bonus


def _compute_overlap(start1: int, end1: int, start2: int, end2: int) -> int:
    return max(0, min(end1, end2) - max(start1, start2))


def _find_program(
    schedule: list[ScheduledProgram],
    target: ScheduledProgram,
) -> ScheduledProgram | None:
    for program in schedule:
        if program.program_id == target.program_id and program.channel_id == target.channel_id:
            return program
    return None


def _max_shift_distance(
    instance: InstanceData,
    state: Solution,
    program: ScheduledProgram,
    mode: Mode,
    border: TargetBorder,
) -> int | None:
    programs = sort_schedule(state.selected.scheduled_programs[:])

    program_idx = None
    for i, scheduled_program in enumerate(programs):
        if (
            scheduled_program.program_id == program.program_id
            and scheduled_program.channel_id == program.channel_id
        ):
            program_idx = i
            break

    if program_idx is None:
        return None

    instance_program = _find_instance_program(instance, program.channel_id, program.program_id)
    if instance_program is None:
        return None

    if mode == Mode.expand:
        if border == TargetBorder.left:
            max_shift_by_instance = program.start - instance_program.start
        else:
            max_shift_by_instance = instance_program.end - program.end
    else:
        max_shift_by_instance = (program.end - program.start) - instance.min_duration

    if max_shift_by_instance <= 0:
        return 0

    distance_to_neighbor = _distance_to_neighbor(programs, program_idx, program, mode, border)
    if distance_to_neighbor <= 0:
        return 0

    distance_to_priority_block = _distance_to_priority_block_constraint(
        instance,
        program,
        mode,
        border,
    )

    return max(
        0,
        min(max_shift_by_instance, distance_to_neighbor, distance_to_priority_block),
    )


def _distance_to_neighbor(
    programs: list[ScheduledProgram],
    program_idx: int,
    program: ScheduledProgram,
    mode: Mode,
    border: TargetBorder,
) -> int:
    if mode == Mode.shrink:
        return 1_000_000

    if border == TargetBorder.left:
        if program_idx == 0:
            return 0
        return max(0, program.start - programs[program_idx - 1].end)

    if program_idx == len(programs) - 1:
        return 0
    return max(0, programs[program_idx + 1].start - program.end)


def _distance_to_priority_block_constraint(
    instance: InstanceData,
    program: ScheduledProgram,
    mode: Mode,
    border: TargetBorder,
) -> int:
    if mode == Mode.shrink:
        return 1_000_000

    min_distance = float("inf")

    for priority_block in instance.priority_blocks:
        channel_allowed = program.channel_id in priority_block.allowed_channels
        if channel_allowed:
            continue

        if border == TargetBorder.left:
            distance = program.start - priority_block.end
            if distance > 0:
                min_distance = min(min_distance, distance)
        else:
            distance = priority_block.start - program.end
            if distance > 0:
                min_distance = min(min_distance, distance)

    return int(min_distance) if min_distance != float("inf") else 1_000_000


def _find_instance_program(
    instance: InstanceData,
    channel_id: int,
    program_id: str,
):
    for channel in instance.channels:
        if channel.channel_id != channel_id:
            continue
        for program in channel.programs:
            if program.program_id == program_id:
                return program
    return None
