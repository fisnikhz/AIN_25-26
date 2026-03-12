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
    
    start_limit = old_program.start
    end_limit = old_program.end
    
    possible_replacements = []
    for channel in instance.channels:
        for p in channel.programs:
            # Check if program is unselected AND fits in the same time period
            if p.program_id in copy.unselected_ids and \
               p.start >= start_limit and \
               p.end <= end_limit:
                
                # We store both the program data and its channel_id
                possible_replacements.append((p, channel.channel_id))

    if not possible_replacements:
        return copy

    # Select a random candidate from any channel
    new_data, new_channel_id = random.choice(possible_replacements)
    
    new_scheduled = ScheduledProgram(
        program_id=new_data.program_id,
        channel_id=new_channel_id, # Use the channel of the new program
        start=new_data.start,
        end=new_data.end
    )

    # --- Uncoment to see channel swap ---
    # if new_channel_id != old_program.channel_id:
    #     print(f"[CHANNEL SWAP] {old_program.program_id} ({old_program.channel_id}) -> "
    #           f"{new_data.program_id} ({new_channel_id}) at {start_limit}-{end_limit}")

    copy.unselect_program(old_program)
    copy.select_program(new_scheduled)
        
    return copy