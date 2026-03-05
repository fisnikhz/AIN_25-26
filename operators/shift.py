from dataclasses import dataclass
from enum import Enum, auto
from copy import deepcopy
from models.solution.solution import Solution
@dataclass(frozen=True)
class ShiftDirection(Enum):
    left = auto()
    right = auto()

def shift(state: Solution, program_id: str, 
          direction: ShiftDirection, shamt: int) -> Solution:
    
    copy = deepcopy(state)
    
    # print(f"shamt: {shamt}, distance(state={state}, program_id={program_id}, direction={direction})={distance(state, program_id, direction)}")
    shamt = max(shamt, distance(copy, program_id, direction))
    
    for program in copy.selected.scheduled_programs:
        if program.program_id == program_id:
            program.start += shamt 
            program.end += shamt
    
    return copy
    
def distance(state: Solution, program_id: str, 
             direction: ShiftDirection) -> int | None:
    
    programs = state.selected.scheduled_programs[1:-1]
    for i in range(1, len(programs)-1):
        if programs[i].program_id == program_id:
            if direction == ShiftDirection.left:
                return programs[i].start - programs[i-1].end
            if direction == ShiftDirection.right:
                return programs[i+1].start - programs[i].end
    return 0
    
