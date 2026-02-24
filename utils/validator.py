def validate_schedule_against_instance(schedule, instance):
    """
    Check that every scheduled program exists in the given instance.
    Raises ValueError with details about each unrecognised entry.
    """
    known = set()
    for channel in instance.channels:
        for program in channel.programs:
            known.add((channel.channel_id, program.program_id))

    mismatches = [
        f"  program_id='{sp.program_id}', channel_id={sp.channel_id}"
        for sp in schedule
        if (sp.channel_id, sp.program_id) not in known
    ]

    if mismatches:
        details = "\n".join(mismatches)
        raise ValueError(
            f"Solution does not match the loaded instance.\n"
            f"{len(mismatches)} scheduled program(s) not found in instance:\n"
            f"{details}\n"
            f"Make sure you selected the correct input/solution pair."
        )
