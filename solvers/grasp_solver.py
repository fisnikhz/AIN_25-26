import random
import time
from copy import deepcopy

from solvers.base_solver import BaseSolver
from models.instance.instance_data import InstanceData
from models.solution.solution import Solution
from models.solution.schedule import Schedule
from models.solution.scheduled_program import ScheduledProgram
from evaluators.evaluator import Evaluator
from operators.replace import replace
from operators.shift_borders import shift_borders, TargetBorder, Mode
from operators.swap import swap
import config.config as config


class GraspSolver:
    """
    GRASP — Greedy Randomized Adaptive Search Procedures.

    Components C = {C1, ..., Cn} are the CHANNELS.
    The score used for the RCL ranking = program.score (the percentage).

    Construction builds a solution from scratch (replaces the old channel selection).
    Local search (for loop) tweaks the constructed solution with hill climbing.
    """

    def __init__(self, evaluator: Evaluator):
        self.evaluator = evaluator

    def solve(self, instance: InstanceData) -> Solution:
        print("\n=== Starting GRASP Optimization ===")
        print(f"Parameters: total_time={config.GRASP_TOTAL_TIME}s, "
              f"p={config.GRASP_P_PERCENTAGE}%, m={config.GRASP_M_ITERATIONS}, "
              f"no_improve_limit={config.GRASP_NO_IMPROVE_LIMIT}")

        best = None  # Best ← □ (null)
        start_time = time.time()
        iteration = 0

        while True:
            elapsed = time.time() - start_time
            if elapsed >= config.GRASP_TOTAL_TIME:
                print(f"Time limit reached ({config.GRASP_TOTAL_TIME}s)")
                break

            iteration += 1

            s = self._greedy_randomized_construction(instance)

            if s is None or len(s.selected) == 0:
                continue

            s = self._local_search(s, instance)

            if best is None or s.fitness > best.fitness:
                print(f"  Iteration {iteration} ({elapsed:.1f}s): "
                      f"New best fitness = {s.fitness}")
                best = s

        total_time = time.time() - start_time
        print(f"\nGRASP completed in {total_time:.2f}s after {iteration} iterations")

        if best is not None:
            print(f"Best fitness: {best.fitness}")
        else:
            print("No valid solution found")

        return best

    def _greedy_randomized_construction(self, instance):
        """
        Build solution S from scratch using channels as components.

        repeat
            C' ← feasible channels (components in C − S)
            if C' is empty then S ← {}          (reset — dead end)
            else
                C'' ← top p% channels by score   (the percentage)
                S ← S ∪ {random channel from C'', pick a program from it}
        until S is a complete solution
        """
        components = instance.channels

        scheduled = []       # S ← {}
        selected_ids = set()
        max_restarts = 50
        restarts = 0

        while restarts < max_restarts:
            feasible_channels = self._get_feasible_channels(
                components, scheduled, selected_ids, instance
            )

            if not feasible_channels:
                # C' is empty
                if len(scheduled) > 0:
                    break
                else:
                    scheduled = []
                    selected_ids = set()
                    restarts += 1
                    continue
            else:
                feasible_channels.sort(key=lambda x: x[1], reverse=True)
                top_count = max(1, int(len(feasible_channels) * config.GRASP_P_PERCENTAGE / 100))
                rcl = feasible_channels[:top_count]

                chosen_channel, _score, feasible_programs = random.choice(rcl)

                program = random.choice(feasible_programs)

                sp = ScheduledProgram(
                    program_id=program.program_id,
                    channel_id=chosen_channel.channel_id,
                    start=program.start,
                    end=program.end
                )
                scheduled.append(sp)
                selected_ids.add(program.program_id)

                scheduled.sort(key=lambda p: (p.start, p.end, p.channel_id))

        if not scheduled:
            return None

        all_ids = set()
        for channel in instance.channels:
            for program in channel.programs:
                all_ids.add(program.program_id)
        unselected_ids = [pid for pid in all_ids if pid not in selected_ids]

        return Solution(
            evaluator=self.evaluator,
            selected=Schedule(scheduled),
            unselected_ids=unselected_ids
        )

    def _get_feasible_channels(self, components, scheduled, selected_ids, instance):
        """
        C' ← channels that have at least one feasible program to add to S.

        Returns list of (channel, channel_score, feasible_programs).
        Each channel is scored via _score_channel (the percentage).
        """
        feasible_channels = []

        for channel in components:
            feasible_programs = []

            for program in channel.programs:
                if program.program_id in selected_ids:
                    continue
                if program.start < instance.opening_time or program.end > instance.closing_time:
                    continue
                if (program.end - program.start) < instance.min_duration:
                    continue
                if self._has_overlap(program, scheduled):
                    continue
                if not self._respects_priority_blocks(program.start, program.end,
                                                      channel.channel_id, instance):
                    continue

                sp = ScheduledProgram(program.program_id, channel.channel_id,
                                      program.start, program.end)
                test_schedule = sorted(scheduled + [sp],
                                       key=lambda p: (p.start, p.end, p.channel_id))
                if not self._respects_genre_limit(test_schedule, instance):
                    continue

                feasible_programs.append(program)

            if feasible_programs:
                channel_score = self._score_channel(feasible_programs)
                feasible_channels.append((channel, channel_score, feasible_programs))

        return feasible_channels

    @staticmethod
    def _score_channel(feasible_programs):
        """
        Score a channel (component) for RCL ranking.

        The score represents the percentage — the highest program.score
        among the channel's feasible programs is used as the channel's value.
        """
        return max(p.score for p in feasible_programs)

    def _local_search(self, s, instance):
        """
        for m times do
            R ← Tweak(Copy(S))
            if Quality(R) > Quality(S) then
                S ← R

        The for loop runs up to m iterations. To determine the right time to
        stop, we track consecutive iterations without improvement. If no
        improvement is found for GRASP_NO_IMPROVE_LIMIT consecutive iterations,
        we stop early — further tweaking is unlikely to yield a better solution.

        Improvement: accept equal-fitness moves to explore plateaus (solutions
        with the same fitness but different structure that may lead to better
        neighbors). Track the best solution separately so we never lose it.
        """
        best_local = s
        no_improve_count = 0

        for i in range(config.GRASP_M_ITERATIONS):
            r = self._tweak(deepcopy(s), instance)  

            if r.fitness > s.fitness:                
                s = r                             
                no_improve_count = 0                
            elif r.fitness == s.fitness:
                s = r
            else:
                no_improve_count += 1

            if s.fitness > best_local.fitness:
                best_local = s

            if no_improve_count >= config.GRASP_NO_IMPROVE_LIMIT:
                break

        return best_local

    @staticmethod
    def _tweak(solution, instance):
        """Tweak(Copy(S)) — same mutation operators as hill climbing."""
        scheduled = list(solution.selected)
        mutation_ops = []

        if len(scheduled) >= 2:
            def swap_op():
                i = random.randrange(len(scheduled))
                possible_j = []
                if i > 0:
                    possible_j.append(i - 1)
                if i < len(scheduled) - 1:
                    possible_j.append(i + 1)
                if possible_j:
                    j = random.choice(possible_j)
                    return swap(instance, solution, scheduled[i], scheduled[j])
                return solution
            mutation_ops.append(swap_op)

        def shift_op():
            program = random.choice(scheduled)
            direction = random.choice(list(TargetBorder))
            mode = random.choice(list(Mode))
            shamt = round(random.random() * config.MAX_SHIFT)
            return shift_borders(instance, solution, program, mode, direction, shamt)
        mutation_ops.append(shift_op)

        def replace_op():
            return replace(solution, instance)
        mutation_ops.append(replace_op)

        op = random.choice(mutation_ops)
        return op()

    @staticmethod
    def _has_overlap(program, scheduled):
        for sp in scheduled:
            if program.start < sp.end and program.end > sp.start:
                return True
        return False

    @staticmethod
    def _respects_priority_blocks(start, end, channel_id, instance):
        for block in instance.priority_blocks:
            overlaps = min(end, block.end) > max(start, block.start)
            if overlaps and channel_id not in block.allowed_channels:
                return False
        return True

    @staticmethod
    def _respects_genre_limit(schedule, instance):
        lookup = {}
        for channel in instance.channels:
            for program in channel.programs:
                lookup[(channel.channel_id, program.program_id)] = program

        consecutive = 0
        last_genre = None
        for sp in schedule:
            key = (sp.channel_id, sp.program_id)
            if key not in lookup:
                return False
            genre = lookup[key].genre
            if genre == last_genre:
                consecutive += 1
            else:
                last_genre = genre
                consecutive = 1
            if consecutive > instance.max_consecutive_genre:
                return False
        return True
