from evaluators.evaluator import Evaluator


class BaseEvaluator(Evaluator):
    """
    Scores a Schedule against an InstanceData according to the problem specification.

    Precomputes instance-derived structures once so that repeated evaluate() calls avoid redundant work.
    """

    def __init__(self, instance):
        self.instance = instance
        self._program_lookup = self._build_program_lookup()

    def _build_program_lookup(self):
        lookup = {}
        for channel in self.instance.channels:
            for program in channel.programs:
                lookup[(channel.channel_id, program.program_id)] = program
        return lookup

    def get_original_program(self, channel_id, program_id):
        return self._program_lookup[(channel_id, program_id)]

    @staticmethod
    def _compute_overlap(start1, end1, start2, end2):
        overlap = min(end1, end2) - max(start1, start2)
        return max(0, overlap)

    def evaluate(self, schedule):
        """
        Compute the total score of a schedule.

        Total Score = sum(popularity scores)
                    + sum(time-preference bonuses)
                    - S * (channel switches)
                    - T * (early terminations + late starts)
        """
        if len(schedule) == 0:
            return 0

        total_score = 0
        channel_switches = 0
        timing_penalties = 0

        for i, sp in enumerate(schedule):
            original = self._program_lookup[(sp.channel_id, sp.program_id)]

            total_score += original.score

            for tp in self.instance.time_preferences:
                if original.genre != tp.preferred_genre:
                    continue
                overlap = self._compute_overlap(sp.start, sp.end, tp.start, tp.end)
                if overlap >= self.instance.min_duration:
                    total_score += tp.bonus

            if sp.start > original.start:
                timing_penalties += 1
            if sp.end < original.end:
                timing_penalties += 1

            if i > 0:
                prev = schedule[i - 1]
                if sp.channel_id != prev.channel_id:
                    channel_switches += 1

        total_score -= self.instance.switch_penalty * channel_switches
        total_score -= self.instance.termination_penalty * timing_penalties

        return total_score
