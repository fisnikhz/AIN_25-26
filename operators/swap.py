import random
from models.solution.solution import Solution
from models.solution.scheduled_program import ScheduledProgram
from models.instance.instance_data import InstanceData

def swap(solution: Solution, instance: InstanceData) -> Solution:
    if not solution.selected or not solution.unselected_ids:
        return solution

    old_program = random.choice(solution.selected)
    
    target_channel_id = old_program.channel_id
    
    channel_programs = []
    for channel in instance.channels:
        if channel.channel_id == target_channel_id:
            channel_programs = channel.programs
            break
            
    possible_replacements = [
        p for p in channel_programs 
        if p.program_id in solution.unselected_ids
    ]

    if not possible_replacements:
        return solution

    new_data = random.choice(possible_replacements)
    
    new_scheduled = ScheduledProgram(
        program_id=new_data.program_id,
        channel_id=target_channel_id,
        start=new_data.start,
        end=new_data.end
    )

    solution.unselect_program(old_program)
    solution.select_program(new_scheduled)
        
    return solution