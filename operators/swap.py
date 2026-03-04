import random
from copy import deepcopy
from models.solution.solution import Solution
from models.solution.scheduled_program import ScheduledProgram
from models.instance.instance_data import InstanceData

def swap(solution: Solution, instance: InstanceData) -> Solution:
    copy = deepcopy(solution)
    
    if not copy.selected or not copy.unselected_ids:
        return copy

    old_program = random.choice(copy.selected)
    
    target_channel_id = old_program.channel_id
    
    channel_programs = []
    for channel in instance.channels:
        if channel.channel_id == target_channel_id:
            channel_programs = channel.programs
            break
            
    possible_replacements = [
        p for p in channel_programs 
        if p.program_id in copy.unselected_ids
    ]

    if not possible_replacements:
        return copy

    new_data = random.choice(possible_replacements)
    
    new_scheduled = ScheduledProgram(
        program_id=new_data.program_id,
        channel_id=target_channel_id,
        start=new_data.start,
        end=new_data.end
    )

    copy.unselect_program(old_program)
    copy.select_program(new_scheduled)
        
    return copy