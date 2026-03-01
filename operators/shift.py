from dataclasses import dataclass
from enum import Enum, auto
from models.solution.solution import Solution

def shift(state: Solution, program_id: str, 
          direction: ShiftDirection, shamt: int) -> Solution:
    
    shamt = max(shamt, distance(state, program_id, direction))
    
    for program in state.selected.scheduled_programs:
        if program.program_id == program_id:
            program.start += shamt 
            program.end += shamt
    
    return state
    
def distance(state: Solution, program_id: str, 
             direction: ShiftDirection) -> int | None:
    
    programs = state.selected.scheduled_programs
    for i in range(len(programs)):
        if programs[0].program_id == program_id:
            if direction == ShiftDirection.left:
                return programs[i].start - programs[i-1].end
            if direction == ShiftDirection.right:
                return programs[i+1].start - programs[0].end
    return None
    

@dataclass(frozen=True)
class ShiftDirection(Enum):
    left = auto()
    right = auto()