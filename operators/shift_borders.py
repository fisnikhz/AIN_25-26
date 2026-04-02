from enum import Enum, auto
from copy import deepcopy

from models.solution.solution import Solution
from models.solution.scheduled_program import ScheduledProgram
from models.instance.instance_data import InstanceData

class TargetBorder(Enum):
    left = auto()
    right = auto()

class Mode(Enum):
    shrink = auto()
    expand = auto()

def shift_borders(instance: InstanceData, state: Solution, program: ScheduledProgram, 
          mode: Mode, border: TargetBorder, shamt: int) -> Solution:
    
    copy = deepcopy(state)
    
    max_shift = _max_shift_distance(instance, copy, program, mode, border)
    # print(f"shamt={shamt}, max_shift={max_shift}")
    shamt = min(abs(shamt), abs(max_shift))
    
    # bone shiftin
    for i, p in enumerate(copy.selected.scheduled_programs):
        if p.program_id == program.program_id:
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
    
    return copy
    
def _max_shift_distance(instance: InstanceData, state: Solution, program: ScheduledProgram, 
                        mode: Mode, border: TargetBorder) -> int | None:

    programs = state.selected.scheduled_programs[:]

    program_idx = None
    for i, p in enumerate(programs):
        if p.program_id == program.program_id:
            program_idx = i
    
    if program_idx is None:
        print(f"⚠️ERROR‼ QIKJO S'BON ME NDODH: \"Program with "
              f"id=\'{program.program_id}\' is not scheduled\".")
        return None
        

    # gjeje objektin e programit ne instance
    for ch in instance.channels:
        if ch.channel_id == program.channel_id:
            for p in ch.programs:
                if p.program_id == program.program_id:
                    instance_program = p

    # kalkulo distancen deri n'kufi t'shfaqjes te kanalit
    if mode == Mode.expand:
        if border == TargetBorder.left:
            max_shift_by_instance = instance_program.start - program.start
        elif border == TargetBorder.right:
            max_shift_by_instance = instance_program.end - program.end
        max_shift_by_instance = abs(max_shift_by_instance)
    # qikjo osht per me kqyr se a je tu e shkrink qe me met ma i shkurt se 30 min duration
    elif mode == Mode.shrink:
        max_shift_by_instance = (program.end - program.start) - instance.min_duration
        if max_shift_by_instance < 0:
            print(f"⚠️ERROR‼ M'KE JEP STATE INVALID): "
                  f"\"Program with id=\'{program.program_id}\' "
                  f"start={program.start} "
                  f"end={program.end}\", "
                  f"Trying to get {border.name} {mode.name} "
                  f"by {max_shift_by_instance}.")
            return None
        max_shift_by_instance = abs(max_shift_by_instance)

    # kalkulo distancen deri te kojshia
    if border == TargetBorder.left and program_idx == 0: 
        distance_to_neighbor = 0
    elif border == TargetBorder.right and program_idx == len(programs)-1:
        distance_to_neighbor = 0
    elif border == TargetBorder.left:
        distance_to_neighbor = programs[program_idx-1].end - program.start
        distance_to_neighbor = abs(distance_to_neighbor)
    elif border == TargetBorder.right:
        distance_to_neighbor = programs[program_idx+1].start - program.end
        distance_to_neighbor = abs(distance_to_neighbor)

    # kalkulo distancen deri te hard constraint-i (priority blocks)
    distance_to_priority_block = _distance_to_priority_block_constraint(
        instance, program, mode, border
    )

    # print(f"max_shift_by_instance:{max_shift_by_instance}, distance_to_neighbor:{distance_to_neighbor}, distance_to_priority_block:{distance_to_priority_block}")
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