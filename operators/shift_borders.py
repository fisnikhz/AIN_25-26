from copy import deepcopy
from enum import Enum, auto

from models.instance.instance_data import InstanceData
from models.solution.scheduled_program import ScheduledProgram
from models.solution.solution import Solution


class TargetBorder(Enum):
    left = auto()
    right = auto()


class Mode(Enum):
    shrink = auto()
    expand = auto()


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
        return copy_state

    shift_amount = min(abs(shamt), abs(max_shift))
    if shift_amount <= 0:
        return copy_state

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

            copy_state.selected.scheduled_programs = _sorted_schedule(
                copy_state.selected.scheduled_programs
            )
            copy_state._fitness = None
            return copy_state

    return copy_state


def _max_shift_distance(
    instance: InstanceData,
    state: Solution,
    program: ScheduledProgram,
    mode: Mode,
    border: TargetBorder,
) -> int | None:
    programs = _sorted_schedule(state.selected.scheduled_programs[:])

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
        instance, program, mode, border
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
    """
    Neighbor limits apply to expansion only.
    Shrink moves reduce occupied time and are not blocked by neighbors.
    User day-edge rule:
    - first program cannot expand left
    - last program cannot expand right
    """
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
    """
    Calculate max expansion distance before entering a disallowed priority block.
    Shrink is always safe w.r.t. this constraint.
    """
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


def _sorted_schedule(schedule: list[ScheduledProgram]) -> list[ScheduledProgram]:
    return sorted(schedule, key=lambda p: (p.start, p.end, p.channel_id, p.program_id))
