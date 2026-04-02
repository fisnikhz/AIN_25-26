from enum import Enum, auto
from copy import deepcopy

import config.config as config
from models.solution.solution import Solution
from models.solution.scheduled_program import ScheduledProgram
from models.instance.instance_data import InstanceData
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

def shift_borders(instance: InstanceData, state: Solution, program: ScheduledProgram, 
          mode: Mode, border: TargetBorder, shamt: int) -> Solution:
    
    copy = deepcopy(state)
    
    max_shift = _max_shift_distance(instance, copy, program, mode, border)
    if max_shift is None:
        return state

    # print(f"shamt={shamt}, max_shift={max_shift}")
    shamt = min(abs(shamt), abs(max_shift))
    if shamt == 0:
        return state
    
    # bone shiftin
    for i, p in enumerate(copy.selected.scheduled_programs):
        if p.program_id == program.program_id and p.channel_id == program.channel_id:
            # print(f"\n--------------------------------------\n"
            #       f"PARA shift:\n"
            #       f"Program(pid={p.program_id}, start={p.start}, end={p.end})\n"
            #       )
            if mode == Mode.shrink:
                if border == TargetBorder.left:
                    copy.selected.scheduled_programs[i].start += shamt 
                elif border == TargetBorder.right:
                    copy.selected.scheduled_programs[i].end -= shamt
            elif mode == Mode.expand:
                if border == TargetBorder.left:
                    copy.selected.scheduled_programs[i].start -= shamt 
                elif border == TargetBorder.right:
                    copy.selected.scheduled_programs[i].end += shamt

            # print(f"\nPAS shift:\n"
            #       f"Program(pid={p.program_id}, start={p.start}, end={p.end})\n"
            #       f"--------------------------------------\n")

    copy.selected.scheduled_programs = sort_schedule(copy.selected.scheduled_programs)
    if not is_schedule_feasible(copy.selected.scheduled_programs, instance):
        return state

    copy._fitness = None
    return copy


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

    for shamt in _candidate_expand_amounts(instance, program, original, border, max_shift):
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
    original,
    border: TargetBorder,
    max_shift: int,
) -> list[int]:
    amounts = {max_shift, min(max_shift, config.MAX_SHIFT)}

    bonus_capture_amount = _bonus_capture_amount(instance, program, original.genre, border, max_shift)
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


def _find_program(schedule: list[ScheduledProgram], target: ScheduledProgram) -> ScheduledProgram | None:
    for program in schedule:
        if program.program_id == target.program_id and program.channel_id == target.channel_id:
            return program
    return None
    
def _max_shift_distance(instance: InstanceData, state: Solution, program: ScheduledProgram, 
                        mode: Mode, border: TargetBorder) -> int | None:

    programs = state.selected.scheduled_programs[:]

    program_idx = None
    for i, p in enumerate(programs):
        if p.program_id == program.program_id and p.channel_id == program.channel_id:
            program_idx = i
    
    if program_idx is None:
        return None
        
    instance_program = None
    for ch in instance.channels:
        if ch.channel_id == program.channel_id:
            for p in ch.programs:
                if p.program_id == program.program_id:
                    instance_program = p
                    break
            if instance_program is not None:
                break
    if instance_program is None:
        return None

    if mode == Mode.expand:
        if border == TargetBorder.left:
            max_shift_by_instance = instance_program.start - program.start
        elif border == TargetBorder.right:
            max_shift_by_instance = instance_program.end - program.end
        max_shift_by_instance = abs(max_shift_by_instance)
    elif mode == Mode.shrink:
        max_shift_by_instance = (program.end - program.start) - instance.min_duration
        if max_shift_by_instance < 0:
            return None
        max_shift_by_instance = abs(max_shift_by_instance)

    # Shrinking moves a border *away* from the adjacent program, so there is no
    # neighbor-based constraint — only expand needs it.
    if mode == Mode.expand:
        if border == TargetBorder.left:
            if program_idx == 0:
                distance_to_neighbor = 0
            else:
                distance_to_neighbor = abs(programs[program_idx - 1].end - program.start)
        else:
            if program_idx == len(programs) - 1:
                distance_to_neighbor = 0
            else:
                distance_to_neighbor = abs(programs[program_idx + 1].start - program.end)
    else:
        distance_to_neighbor = float('inf')

    distance_to_priority_block = _distance_to_priority_block_constraint(
        instance, program, mode, border
    )

    return min(max_shift_by_instance, distance_to_neighbor, distance_to_priority_block)

def _distance_to_priority_block_constraint(instance: InstanceData, program: ScheduledProgram, 
                                           mode: Mode, border: TargetBorder) -> int:
    """
    Calculate how far we can shift without violating priority block constraints.
    Priority blocks define which channels are allowed in specific time windows.
    """
    min_distance = float('inf')
    
    # Check all priority blocks for conflicts
    for pb in instance.priority_blocks:
        # Is this channel allowed in this priority block?
        channel_allowed_in_block = program.channel_id in pb.allowed_channels
        
        if mode == Mode.expand and not channel_allowed_in_block:
            # If expanding into a block where this channel is NOT allowed
            if border == TargetBorder.left:
                # Expanding left: can't go earlier than where the block ends
                distance = program.start - pb.end
                if distance > 0:  # Block ends before current start
                    min_distance = min(min_distance, distance)
            elif border == TargetBorder.right:
                # Expanding right: can't go later than where the block starts
                distance = pb.start - program.end
                if distance > 0:  # Block starts after current end
                    min_distance = min(min_distance, distance)
    
    return min_distance if min_distance != float('inf') else 1000000
