import random
from copy import deepcopy

from models.instance.instance_data import InstanceData
from models.solution.scheduled_program import ScheduledProgram
from models.solution.solution import Solution
from utils.schedule_feasibility import build_program_lookup, respects_genre_limit, respects_priority_blocks, sort_schedule


# ---------------------------------------------------------------------------
# Heuristic replace: remove the weakest contributor, insert the best candidate
# ---------------------------------------------------------------------------

def replace_heuristic(solution: Solution, instance: InstanceData) -> Solution:
    """
    Guided replace:
    1. Score every scheduled program by its marginal contribution
       (popularity + time-pref bonuses − switch penalties it causes).
    2. Try to remove the lowest-value program first.
    3. From valid replacements, pick the candidate with the highest value,
       favouring the same channel as adjacent programs to avoid new switch penalties.
    """
    copy = deepcopy(solution)

    if len(copy.selected) == 0 or not copy.unselected_ids:
        return solution

    ordered = sort_schedule(copy.selected.scheduled_programs)
    lookup = build_program_lookup(instance)

    # Score each scheduled program by marginal value (ascending → weakest first)
    scored = [
        (p, _marginal_score(p, idx, ordered, instance, lookup))
        for idx, p in enumerate(ordered)
    ]
    scored.sort(key=lambda x: x[1])  # weakest first

    for old_program, _ in scored:
        old_index = _find_program_index(ordered, old_program)
        if old_index is None:
            continue

        gap_start = instance.opening_time if old_index == 0 else ordered[old_index - 1].end
        gap_end   = instance.closing_time  if old_index == len(ordered) - 1 else ordered[old_index + 1].start

        candidates = _valid_replacements(
            gap_start=gap_start,
            gap_end=gap_end,
            unselected_ids=set(copy.unselected_ids),
            instance=instance,
        )

        if not candidates:
            continue

        # Determine the preferred channel(s) of the neighbours to avoid new switch penalty
        preferred_channels: set[int] = set()
        if old_index > 0:
            preferred_channels.add(ordered[old_index - 1].channel_id)
        if old_index < len(ordered) - 1:
            preferred_channels.add(ordered[old_index + 1].channel_id)

        # Sort candidates: descending by (score + channel-continuity bonus)
        def _candidate_key(c):
            prog, ch_id = c
            continuity = instance.switch_penalty if ch_id in preferred_channels else 0
            tp_bonus   = _time_pref_bonus(prog, instance)
            return prog.score + continuity + tp_bonus

        candidates.sort(key=_candidate_key, reverse=True)
        new_program, new_channel_id = candidates[0]

        ordered[old_index] = ScheduledProgram(
            program_id=new_program.program_id,
            channel_id=new_channel_id,
            start=new_program.start,
            end=new_program.end,
        )

        if not respects_genre_limit(ordered, instance, lookup):
            ordered[old_index] = old_program
            continue

        copy.selected.scheduled_programs = ordered
        if old_program.program_id not in copy.unselected_ids:
            copy.unselected_ids.append(old_program.program_id)
        if new_program.program_id in copy.unselected_ids:
            copy.unselected_ids.remove(new_program.program_id)
        copy._fitness = None
        return copy

    return solution


# ---------------------------------------------------------------------------
# Helper: per-program marginal score
# ---------------------------------------------------------------------------

def _marginal_score(
    sp: ScheduledProgram,
    idx: int,
    ordered: list,
    instance: InstanceData,
    lookup: dict,
) -> float:
    """
    Estimate the fitness contribution of a single scheduled program:
      + popularity score
      + time-preference bonus (if genre overlaps a preference window)
      - switch penalty for each neighbouring boundary that crosses a channel
    """
    prog = lookup.get((sp.channel_id, sp.program_id))
    if prog is None:
        return 0.0

    value = float(prog.score)
    value += _time_pref_bonus(prog, instance)

    # Penalise switch boundaries that this program is responsible for
    if idx > 0 and ordered[idx - 1].channel_id != sp.channel_id:
        value -= instance.switch_penalty
    if idx < len(ordered) - 1 and ordered[idx + 1].channel_id != sp.channel_id:
        value -= instance.switch_penalty

    # Penalise timing drift
    if sp.start > prog.start:
        value -= instance.termination_penalty
    if sp.end < prog.end:
        value -= instance.termination_penalty

    return value


def _time_pref_bonus(prog, instance: InstanceData) -> float:
    """Return total time-preference bonus the program can earn."""
    bonus = 0.0
    for tp in instance.time_preferences:
        if prog.genre != tp.preferred_genre:
            continue
        overlap = min(prog.end, tp.end) - max(prog.start, tp.start)
        if overlap >= instance.min_duration:
            bonus += tp.bonus
    return bonus


# ---------------------------------------------------------------------------
# Original random replace (kept for exploration)
# ---------------------------------------------------------------------------

def replace(solution: Solution, instance: InstanceData) -> Solution:
    copy = deepcopy(solution)

    if len(copy.selected) == 0 or not copy.unselected_ids:
        return solution

    ordered = sort_schedule(copy.selected.scheduled_programs)
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

        if not respects_genre_limit(ordered, instance):
            ordered[old_index] = old_program
            continue

        copy.selected.scheduled_programs = ordered
        if old_program.program_id not in copy.unselected_ids:
            copy.unselected_ids.append(old_program.program_id)
        if new_program.program_id in copy.unselected_ids:
            copy.unselected_ids.remove(new_program.program_id)
        copy._fitness = None
        return copy

    return solution


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

            if (program.end - program.start) < instance.min_duration:
                continue

            if not respects_priority_blocks(program.start, program.end, channel.channel_id, instance):
                continue

            candidates.append((program, channel.channel_id))

    return candidates


def _fits_gap(start: int, end: int, gap_start: int, gap_end: int) -> bool:
    return start >= gap_start and end <= gap_end and start < end


def _has_valid_program_duration(program) -> bool:
    return program.end > program.start
def _find_program_index(schedule: list[ScheduledProgram], target: ScheduledProgram) -> int | None:
    for index, program in enumerate(schedule):
        if program.program_id == target.program_id and program.channel_id == target.channel_id:
            return index
    return None
