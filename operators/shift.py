from enum import Enum, auto
from copy import deepcopy

from models.solution.solution import Solution
from models.solution.scheduled_program import ScheduledProgram
from models.instance.instance_data import InstanceData

class ShiftDirection(Enum):
    left = auto()
    right = auto()

def shift(instance: InstanceData, state: Solution, program: ScheduledProgram, 
          direction: ShiftDirection, shamt: int) -> Solution:
    
    copy = deepcopy(state)
    
    max_shift = _max_shift_distance(instance, copy, program, direction)
    # print(f"shamt={shamt}, max_shift={max_shift}")
    shamt = min(abs(shamt), abs(max_shift))
    
    # bone shiftin
    for i, p in enumerate(copy.selected.scheduled_programs):
        if p.program_id == program.program_id:
            # print(f"\n--------------------------------------\n"
            #       f"PARA shift:\n"
            #       f"Program(pid={p.program_id}, start={p.start}, end={p.end})\n"
            #       )
            if direction == ShiftDirection.left:
                copy.selected.scheduled_programs[i].start -= shamt 
                copy.selected.scheduled_programs[i].end -= shamt
            elif direction == ShiftDirection.right:
                copy.selected.scheduled_programs[i].start += shamt 
                copy.selected.scheduled_programs[i].end += shamt

            # print(f"\nPAS shift:\n"
            #       f"Program(pid={p.program_id}, start={p.start}, end={p.end})\n"
            #       f"--------------------------------------\n")
    
    return copy
    
def _max_shift_distance(instance: InstanceData, state: Solution, program: ScheduledProgram, 
                        direction: ShiftDirection) -> tuple[int, int] | None:

    programs = state.selected.scheduled_programs[:]

    program_idx = None
    for i, p in enumerate(programs):
        if p.program_id == program.program_id:
            program_idx = i
    
    if program_idx is None:
        print(f"Program with id \'{program.program_id} is not scheduled\'")
        exit(1)

    # gjeje objektin e programit ne instance
    for ch in instance.channels:
        if ch.channel_id == program.channel_id:
            for p in ch.programs:
                if p.program_id == program.program_id:
                    instance_program = p

    # kalkulo distancen deri n'kufi t'shfaqjes te kanalit
    if direction == ShiftDirection.left:
        distance_to_end = instance_program.start - program.start
    elif direction == ShiftDirection.right:
        distance_to_end = instance_program.end - program.end
    distance_to_end = abs(distance_to_end)

    # kalkulo distnacen deri te kojshia
    if direction == ShiftDirection.left and program_idx == 0: 
        distance_to_neighbor = 0
    elif direction == ShiftDirection.right and program_idx == len(programs)-1:
        distance_to_neighbor = 0
    elif direction == ShiftDirection.left:
        distance_to_neighbor = programs[program_idx-1].end - program.start
        distance_to_neighbor = abs(distance_to_neighbor)
    elif direction == ShiftDirection.right:
        distance_to_neighbor = programs[program_idx+1].start - program.end
        distance_to_neighbor = abs(distance_to_neighbor)
    

    # print(f"distance_to_end:{distance_to_end}, distance_to_neighbor:{distance_to_neighbor}")
    return min(distance_to_end, distance_to_neighbor)