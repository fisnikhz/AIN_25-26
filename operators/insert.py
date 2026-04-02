"""
INSERT Operator - Insertion i programit unselected ku ka hapësirë.

Ky operator:
1. Merr një program UNSELECTED
2. E inserton ku ka HAPËSIRË (gap) në schedule
3. Aktivizohet çdo N iteracione (parametër, p.sh. 100)
4. Ekzekutohet PARA random restart

Përdorim HashMap për O(1) lookups.
"""

import random
from copy import deepcopy
from typing import Dict, List, Tuple, Optional

from models.instance.instance_data import InstanceData
from models.solution.solution import Solution
from models.solution.scheduled_program import ScheduledProgram


def insert(solution: Solution, instance: InstanceData) -> Solution:
    """
    INSERT Operator: Merr program unselected dhe e inserton ku ka hapësirë.
    VERSION I SIGURT - Kontrollon të gjitha constraints.
    
    Args:
        solution: Zgjidhja aktuale
        instance: Instance data
    
    Returns:
        Solution e re me programin e insertuar (ose origjinale nëse s'ka mundësi)
    """
    copy = deepcopy(solution)
    
    # Kontrollo nëse ka programe unselected
    if not copy.unselected_ids:
        return copy
    
    # Sorto programet sipas kohës
    scheduled = _sorted_schedule(copy.selected.scheduled_programs)
    
    # Gjej GAPS (hapësirat) në schedule
    gaps = _find_gaps(scheduled, instance)
    
    if not gaps:
        return copy
    
    # Ndërto HashMap për O(1) lookup
    program_lookup = _build_program_lookup(instance)
    
    # Provo të insertosh çdo program unselected
    for program_id in copy.unselected_ids[:]:
        # VERIFIKIM EXTRA: Sigurohu që ky program NUK është tashmë në schedule
        if any(sp.program_id == program_id for sp in copy.selected.scheduled_programs):
            # Program tashmë ekziston në schedule - hiqe nga unselected
            if program_id in copy.unselected_ids:
                copy.unselected_ids.remove(program_id)
            continue
        
        program_info = _find_program_in_instance(program_id, instance)
        if program_info is None:
            continue
        
        program, channel_id = program_info
        duration = program.end - program.start
        
        # Provo çdo gap
        for gap_start, gap_end in gaps:
            gap_duration = gap_end - gap_start
            
            # Kontrollo nëse programi FITET në gap
            if duration <= gap_duration:
                # Kontrollo time bounds
                if not _respects_time_bounds(gap_start, gap_start + duration, instance):
                    continue
                
                # Kontrollo min duration
                if not _respects_min_duration(gap_start, gap_start + duration, instance):
                    continue
                
                # Kontrollo priority blocks
                if not _respects_priority_blocks(gap_start, gap_start + duration, channel_id, instance):
                    continue
                
                # KRITIKE: Kontrollo që kohët ORIGJINALE të programit janë brenda gap
                # Programi duhet të vendoset me kohët e tij origjinale, jo me gap times!
                if not (program.start >= gap_start and program.end <= gap_end):
                    # Kohët origjinale të programit NUK janë brenda gap
                    continue
                
                # Krijo programin me kohët e tij ORIGJINALE
                new_sp = ScheduledProgram(
                    program_id=program.program_id,
                    channel_id=channel_id,
                    start=program.start,  # KOHË ORIGJINALE
                    end=program.end       # KOHË ORIGJINALE
                )
                
                # Shto përkohësisht në schedule për të testuar
                test_schedule = copy.selected.scheduled_programs + [new_sp]
                test_schedule = _sorted_schedule(test_schedule)
                
                # Kontrollo no overlap
                if not _respects_no_overlap(test_schedule):
                    continue
                
                # Kontrollo genre limit
                if _respects_genre_limit(test_schedule, instance):
                    # Shto në schedule
                    copy.selected.scheduled_programs = test_schedule
                    
                    # Hiq nga unselected
                    if program_id in copy.unselected_ids:
                        copy.unselected_ids.remove(program_id)
                    
                    # Invalido fitness
                    copy._fitness = None
                    
                    return copy
    
    return copy


def insert_best(solution: Solution, instance: InstanceData) -> Solution:
    """
    INSERT BEST: Inserton programin unselected me SCORE më të lartë.
    """
    copy = deepcopy(solution)
    
    if not copy.unselected_ids:
        print(f"    INSERT DEBUG: Nuk ka programe unselected ({len(copy.unselected_ids)})")
        return copy
    
    scheduled = _sorted_schedule(copy.selected.scheduled_programs)
    gaps = _find_gaps(scheduled, instance)
    
    if not gaps:
        print(f"    INSERT DEBUG: Nuk ka gaps ({len(gaps)})")
        return copy
    
    print(f"    INSERT DEBUG: {len(copy.unselected_ids)} unselected, {len(gaps)} gaps")
    
    # Gjej programin me score më të lartë që fitet
    best_candidate = None
    best_score = -1
    best_gap = None
    
    checked_programs = 0
    fits_in_gap = 0
    passes_constraints = 0
    
    for program_id in copy.unselected_ids:
        # VERIFIKIM EXTRA: Sigurohu që ky program NUK është tashmë në schedule
        if any(sp.program_id == program_id for sp in copy.selected.scheduled_programs):
            continue
        
        program_info = _find_program_in_instance(program_id, instance)
        if program_info is None:
            continue
        
        program, channel_id = program_info
        duration = program.end - program.start
        checked_programs += 1
        
        for gap_start, gap_end in gaps:
            if duration <= (gap_end - gap_start):
                # KRITIKE: Kontrollo që kohët ORIGJINALE të programit janë brenda gap
                if not (program.start >= gap_start and program.end <= gap_end):
                    continue
                
                fits_in_gap += 1
                
                # Kontrollo time bounds
                if not _respects_time_bounds(program.start, program.end, instance):
                    continue
                
                # Kontrollo min duration
                if not _respects_min_duration(program.start, program.end, instance):
                    continue
                
                # Kontrollo priority blocks
                if not _respects_priority_blocks(program.start, program.end, channel_id, instance):
                    continue
                
                # Test kandidatin me kohët ORIGJINALE
                test_sp = ScheduledProgram(
                    program_id=program.program_id,
                    channel_id=channel_id,
                    start=program.start,  # KOHË ORIGJINALE
                    end=program.end       # KOHË ORIGJINALE
                )
                test_schedule = copy.selected.scheduled_programs + [test_sp]
                test_schedule = _sorted_schedule(test_schedule)
                
                # Kontrollo no overlap
                if not _respects_no_overlap(test_schedule):
                    continue
                
                # Kontrollo genre limit dhe update best
                if _respects_genre_limit(test_schedule, instance) and program.score > best_score:
                    passes_constraints += 1
                    best_score = program.score
                    best_candidate = (program, channel_id)
                    best_gap = (program.start, program.end)  # Use original times
    
    print(f"    INSERT DEBUG: Checked {checked_programs} programs, {fits_in_gap} fit in gaps, {passes_constraints} pass constraints")
    
    if best_candidate and best_gap:
        program, channel_id = best_candidate
        # Përdor kohët ORIGJINALE të programit
        new_sp = ScheduledProgram(
            program_id=program.program_id,
            channel_id=channel_id,
            start=program.start,  # KOHË ORIGJINALE
            end=program.end       # KOHË ORIGJINALE
        )
        
        # Kontrollo një herë të fundit me të gjitha constraints
        test_schedule = copy.selected.scheduled_programs + [new_sp]
        test_schedule = _sorted_schedule(test_schedule)
        
        if (_respects_no_overlap(test_schedule) and 
            _respects_genre_limit(test_schedule, instance)):
            copy.selected.scheduled_programs = test_schedule
            
            if program.program_id in copy.unselected_ids:
                copy.unselected_ids.remove(program.program_id)
            
            copy._fitness = None
            print(f"    INSERT SUCCESS: Program {program.program_id} (score={program.score}) inserted!")
        else:
            print(f"    INSERT FAIL: Final validation failed for {program.program_id}")
    else:
        print(f"    INSERT FAIL: No suitable candidates found")
    
    return copy


def _find_gaps(scheduled: List[ScheduledProgram], instance: InstanceData) -> List[Tuple[int, int]]:
    """
    Gjej GAPS (hapësirat) GLOBALE në schedule ku mund të insertohet një program.
    
    Gap ekziston vetëm nëse asnjë program NUK mbulon atë kohë.
    
    Returns:
        Lista e tuple-ave (gap_start, gap_end)
    """
    if not scheduled:
        # Nëse schedule është bosh, e gjithë periudha është gap
        return [(instance.opening_time, instance.closing_time)]
    
    # Krijo një listë të të gjitha kohërave të zëna
    # Për çdo kohë, shëno nëse ka programe që po ekzekutohen
    time_points = []
    for sp in scheduled:
        time_points.append((sp.start, 'start'))
        time_points.append((sp.end, 'end'))
    
    # Sorto sipas kohës
    time_points.sort(key=lambda x: x[0])
    
    # Gjej gaps duke numëruar programe aktive
    gaps = []
    active_programs = 0
    last_time = instance.opening_time
    
    # Kontrollo gap në fillim
    if time_points and time_points[0][0] > instance.opening_time:
        gaps.append((instance.opening_time, time_points[0][0]))
        last_time = time_points[0][0]
    
    for time, event_type in time_points:
        if event_type == 'start':
            # Nëse nuk ka programe aktive, dhe ka kaluar kohë, ky është një gap
            if active_programs == 0 and time > last_time:
                gaps.append((last_time, time))
            active_programs += 1
        else:  # 'end'
            active_programs -= 1
            if active_programs == 0:
                last_time = time
    
    # Kontrollo gap në fund
    if active_programs == 0 and last_time < instance.closing_time:
        gaps.append((last_time, instance.closing_time))
    
    return gaps


def _find_program_in_instance(program_id: str, instance: InstanceData) -> Optional[Tuple[object, int]]:
    """Gjej program në instance sipas ID."""
    for channel in instance.channels:
        for program in channel.programs:
            if program.program_id == program_id:
                return (program, channel.channel_id)
    return None


def _build_program_lookup(instance: InstanceData) -> Dict[Tuple[int, str], object]:
    """Ndërto HashMap për O(1) lookup."""
    lookup = {}
    for channel in instance.channels:
        for program in channel.programs:
            lookup[(channel.channel_id, program.program_id)] = program
    return lookup


def _respects_priority_blocks(start: int, end: int, channel_id: int, instance: InstanceData) -> bool:
    """Kontrollo nëse respekton priority block constraints."""
    for block in instance.priority_blocks:
        overlaps = min(end, block.end) > max(start, block.start)
        if overlaps and channel_id not in block.allowed_channels:
            return False
    return True


def _respects_no_overlap(schedule: List[ScheduledProgram]) -> bool:
    """
    Kontrollo që programet të mos kenë overlap BRENDA TË NJËJTIT KANAL.
    Programet në kanale të ndryshme MUND të overlap në kohë.
    Schedule duhet të jetë i sortuar sipas kohës.
    """
    if not schedule:
        return True
    
    # Grupo programet sipas kanalit
    channels_programs = {}
    for sp in schedule:
        # Kontrollo që start < end
        if sp.start >= sp.end:
            return False
        
        if sp.channel_id not in channels_programs:
            channels_programs[sp.channel_id] = []
        channels_programs[sp.channel_id].append(sp)
    
    # Kontrollo overlap PER KANAL
    for channel_id, programs in channels_programs.items():
        # Sorto programet e këtij kanali sipas kohës
        sorted_programs = sorted(programs, key=lambda p: (p.start, p.end))
        
        # Kontrollo overlap midis programeve në të njëjtin kanal
        for i in range(len(sorted_programs) - 1):
            if sorted_programs[i].end > sorted_programs[i + 1].start:
                # Overlap në të njëjtin kanal - GABIM!
                return False
    
    return True
    
    return True


def _respects_time_bounds(start: int, end: int, instance: InstanceData) -> bool:
    """Kontrollo që programi të jetë brenda opening/closing time."""
    return start >= instance.opening_time and end <= instance.closing_time


def _respects_min_duration(start: int, end: int, instance: InstanceData) -> bool:
    """Kontrollo që programi të ketë min duration."""
    return (end - start) >= instance.min_duration


def _respects_genre_limit(schedule: List[ScheduledProgram], instance: InstanceData) -> bool:
    """
    Kontrollo nëse schedule respekton max_consecutive_genre constraint.
    """
    if not schedule:
        return True
    
    lookup = _build_program_lookup(instance)
    consecutive = 0
    last_genre = None
    
    for sp in schedule:
        program = lookup.get((sp.channel_id, sp.program_id))
        if program is None:
            continue
        
        genre = program.genre
        if genre == last_genre:
            consecutive += 1
        else:
            last_genre = genre
            consecutive = 1
        
        if consecutive > instance.max_consecutive_genre:
            return False
    
    return True


def _sorted_schedule(schedule: List[ScheduledProgram]) -> List[ScheduledProgram]:
    """Sorto schedule sipas kohës."""
    return sorted(
        schedule,
        key=lambda p: (p.start, p.end, p.channel_id, p.program_id)
    )
