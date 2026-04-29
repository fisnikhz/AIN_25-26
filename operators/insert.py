import random
from copy import deepcopy
from typing import Dict, List, Optional, Tuple

from models.instance.instance_data import InstanceData
from models.solution.scheduled_program import ScheduledProgram
from models.solution.solution import Solution


def insert_best(solution: Solution, instance: InstanceData) -> Solution:
    state = deepcopy(solution)
    if not state.unselected_ids:
        return state

    gaps = _find_gaps_per_channel(state.selected.scheduled_programs, instance)
    if not gaps:
        return state

    best_overall_solution = None
    best_fitness = state.fitness

    for program_id in list(state.unselected_ids):
        # Gjejmë kanalin origjinal ku ky program lejohet
        prog_info = _find_program(instance, program_id)
        if not prog_info:
            continue

        _, allowed_channel_id = prog_info

        relevant_gaps = [g for g in gaps if g[2] == allowed_channel_id]
        if not relevant_gaps:
            continue

        candidate = _best_program_insertion(state, instance, program_id, relevant_gaps)

        if candidate and candidate.fitness > best_fitness:
            best_overall_solution = candidate
            best_fitness = candidate.fitness

    return best_overall_solution if best_overall_solution else state


def _best_program_insertion(
        base: Solution,
        instance: InstanceData,
        program_id: str,
        gaps: List[Tuple[int, int, int]],
) -> Optional[Solution]:
    prog_info = _find_program(instance, program_id)
    program, channel_id = prog_info

    best_local_solution = None
    best_local_fitness = float("-inf")

    for g_start, g_end, g_channel_id in gaps:
        # Mos lejo insertion në kanal tjetër nga ai origjinali
        if g_channel_id != channel_id:
            continue

        windows = _candidate_windows(
            program.start, program.end, g_start, g_end,
            instance.min_duration, instance.opening_time, instance.closing_time
        )

        for start, end in windows:
            if not _is_feasible(base, instance, program_id, g_channel_id, start, end):
                continue

            candidate = deepcopy(base)
            sp = ScheduledProgram(
                program_id=program_id,
                channel_id=g_channel_id,
                start=start,
                end=end
            )

            candidate.selected.scheduled_programs.append(sp)
            candidate.selected.scheduled_programs = _sorted_schedule(candidate.selected.scheduled_programs)

            if program_id in candidate.unselected_ids:
                candidate.unselected_ids.remove(program_id)

            candidate._fitness = None

            try:
                # Kontrollojmë nëse fitness llogaritet pa gabime (KeyError)
                curr_fitness = candidate.fitness
                if curr_fitness > best_local_fitness:
                    best_local_solution = candidate
                    best_local_fitness = curr_fitness
            except KeyError:
                continue

    return best_local_solution


def _find_gaps_per_channel(schedule: List[ScheduledProgram], instance: InstanceData) -> List[Tuple[int, int, int]]:
    all_gaps = []
    for channel in instance.channels:
        ch_id = channel.channel_id
        ch_programs = sorted(
            [sp for sp in schedule if sp.channel_id == ch_id],
            key=lambda x: x.start
        )
        cursor = instance.opening_time
        for sp in ch_programs:
            if sp.start > cursor:
                all_gaps.append((cursor, sp.start, ch_id))
            cursor = max(cursor, sp.end)
        if cursor < instance.closing_time:
            all_gaps.append((cursor, instance.closing_time, ch_id))
    return all_gaps


def _is_feasible(solution, instance, pid, channel_id, start, end) -> bool:
    if start >= end or (end - start) < instance.min_duration:
        return False
    if not (instance.opening_time <= start and end <= instance.closing_time):
        return False
    if not _respects_priority(start, end, channel_id, instance):
        return False
    # 2. Overlap Check (Strikt brenda kanalit)
    new_sp = ScheduledProgram(pid, channel_id, start, end)

    # Marrim programet ekzistuese të atij kanali + programin e ri
    current_channel_progs = [p for p in solution.selected.scheduled_programs if p.channel_id == channel_id]
    current_channel_progs.append(new_sp)

    # I sortojmë sipas kohës së fillimit
    ch_progs = sorted(current_channel_progs, key=lambda x: x.start)

    for i in range(len(ch_progs) - 1):
        # Nëse fundi i programit aktual është më i madh se fillimi i tjetrit -> ERROR
        if ch_progs[i].end > ch_progs[i + 1].start:
            return False


def _genre_limit(schedule, instance):
    lookup = {(c.channel_id, p.program_id): p for c in instance.channels for p in c.programs}
    sorted_sch = _sorted_schedule(schedule)
    last_g, count = None, 0
    for sp in sorted_sch:
        prog = lookup.get((sp.channel_id, sp.program_id))
        if not prog: continue
        if prog.genre == last_g:
            count += 1
        else:
            last_g, count = prog.genre, 1
        if count > instance.max_consecutive_genre: return False
    return True


def _sorted_schedule(schedule):
    return sorted(schedule, key=lambda x: (x.start, x.end, x.channel_id, x.program_id))


def _find_program(instance, pid):
    for c in instance.channels:
        for p in c.programs:
            if p.program_id == pid:
                return p, c.channel_id
    return None


def _respects_priority(start, end, channel_id, instance):
    for b in instance.priority_blocks:
        if min(end, b.end) > max(start, b.start):
            if channel_id not in b.allowed_channels: return False
    return True


def _candidate_windows(p_start, p_end, g_start, g_end, min_d, open_t, close_t):
    # l (left) është pika më e hershme ku mund të fillojë:
    # brenda gap-it dhe orarit të hapjes (pa kufizim nga p_start)
    l = max(g_start, open_t)

    # r (right) është pika më e vonshme ku mund të mbarojë:
    # brenda gap-it dhe orarit të mbylljes (pa kufizim nga p_end)
    r = min(g_end, close_t)

    # Nëse pas shkurtimit, kohëzgjatja është më e vogël se min_duration,
    # ky program nuk mund të futet në këtë gap.
    if r - l < min_d:
        return []

    # Kthejmë dritaret e mundshme të shkurtuara saktë
    return [
        (l, r),  # Kohëzgjatja maksimale brenda gap-it
        (l, l + min_d),  # Vetëm kohëzgjatja minimale nga fillimi
        (r - min_d, r)  # Vetëm kohëzgjatja minimale në fund
    ]


def insertion_stats(solution, instance):
    # Thërrasim gjetjen e gaps
    gaps = _find_gaps_per_channel(solution.selected.scheduled_programs, instance)

    # Kthejmë fjalorin me të dhëna
    return {
        "gaps": len(gaps),
        "unselected": len(solution.unselected_ids),
        "placeable_any": 1 if len(gaps) > 0 and len(solution.unselected_ids) > 0 else 0
        # Mund ta bësh edhe më kompleks duke kontrolluar feasibility për çdo program,
        # por kjo mund ta ngadalësojë shumë ILS-in.
    }

def insert(solution, instance):
    return insert_best(solution, instance)