from __future__ import annotations
import bisect
import random
from typing import Optional
from scheduling_intelligent_ils.beam_search_scheduler import BeamSearchScheduler
from scheduling_intelligent_ils.common import CandidateSegment, CandidateSolution, InstanceContext
from scheduling_intelligent_ils.smart_tv_scheduler_scoreboost import SmartTVSchedulerScoreBoost

class AdaptiveHybridILSScheduler:
#1
    def __init__(self, instance_data, random_seed: int = 20260413, max_iterations: Optional[int] = None, verbose: bool = False):
        self.instance_data = instance_data
        self.context = InstanceContext(instance_data)
        self.verbose = verbose
        self.random = random.Random(random_seed)
        scale = sum(len(channel.programs) for channel in instance_data.channels)
        
        if scale <= 300:
            cfg = (80, 10, 28, 36, 6, 6, 4, 4)
        elif scale <= 2500:
            cfg = (150, 8, 22, 24, 5, 7, 4, 3)
        elif scale <= 9000:
            cfg = (260, 6, 16, 16, 4, 8, 3, 2)
        else:
            cfg = (320, 4, 12, 10, 4, 10, 2, 1)

        (self.seed_beam_width, self.catalog_top_k, self.window_beam_width, 
         default_iterations, self.elite_size, self.max_block_size, 
         self.neighborhood_trials, self.polish_rounds) = cfg
         
        self.max_iterations = max_iterations or default_iterations
        self.catalog, self.catalog_starts = [], []
        self.catalog_signatures = set()
        self.elite_pool = []
#5
    def marginal_value(self, programs: list[CandidateSegment], index: int) -> float:
        item = programs[index]
        value = float(item.fitness)
        
        has_previous = index > 0
        has_next = index + 1 < len(programs)

        if has_previous:
            previous_item = programs[index - 1]
            if previous_item.channel_id != item.channel_id:
                value -= self.context.switch_penalty / 2
            if previous_item.genre == item.genre:
                value -= 1.5

        if has_next:
            next_item = programs[index + 1]
            if next_item.channel_id != item.channel_id:
                value -= self.context.switch_penalty / 2
            if next_item.genre == item.genre:
                value -= 1.5

        return value
#6
    def find_weakest_index(self, programs: list[CandidateSegment]) -> int:
        worst_score = float('inf')
        worst_index = 0
        
        for i in range(len(programs)):
            current_score = self.marginal_value(programs, i)
            if current_score < worst_score:
                worst_score = current_score
                worst_index = i
                
        return worst_index
#7
    def get_window(self, center_idx: int, size: int, total_len: int) -> tuple[int, int]:
        start = center_idx - size // 2
        if start < 0:
            start = 0
            
        end = start + size
        if end > total_len:
            end = total_len
            
        final_start = end - size
        if final_start < 0:
            final_start = 0
            
        return final_start, end
#3
    def build_catalog(self, seeds: list[CandidateSolution]):
        for sol in seeds:
            for item in sol.scheduled_programs:
                sig = item.signature()
                if sig not in self.catalog_signatures:
                    self.catalog_signatures.add(sig)
                    self.catalog.append(item)
                    
        self.catalog.sort(key=lambda x: x.start)
        for x in self.catalog:
            self.catalog_starts.append(x.start)
#4
    def register_elite(self, solution: CandidateSolution):
        sig = solution.signature()
        
        for i in range(len(self.elite_pool)):
            elite = self.elite_pool[i]
            if elite.signature() == sig:
                if solution.total_score > elite.total_score:
                    self.elite_pool[i] = solution.clone()
                return
                
        self.elite_pool.append(solution.clone())
        self.elite_pool.sort(key=lambda x: x.total_score, reverse=True)
        
        if len(self.elite_pool) > self.elite_size:
            self.elite_pool = self.elite_pool[:self.elite_size]
#8
    def repair_window(self, solution: CandidateSolution, start_idx: int, end_idx: int, guide: Optional[CandidateSolution]) -> CandidateSolution:
        prefix = solution.scheduled_programs[:start_idx]
        suffix = solution.scheduled_programs[end_idx:]
        
        if len(prefix) > 0:
            left_bound = prefix[-1].end
        else:
            left_bound = self.context.opening_time
            
        if len(suffix) > 0:
            right_bound = suffix[0].start
        else:
            right_bound = self.context.closing_time
            
        if right_bound < left_bound:
            return solution

        used_ids = set()
        for p in prefix:
            used_ids.add(p.unique_program_id)
        for p in suffix:
            used_ids.add(p.unique_program_id)
            
        pool = []
        for p in self.catalog:
            if p.start >= left_bound and p.end <= right_bound:
                if p.unique_program_id not in used_ids:
                    pool.append(p)
                    
        guide_sigs = set()
        if guide is not None:
            for p in guide.scheduled_programs:
                guide_sigs.add(p.signature())

        if len(prefix) > 0:
            prev_chan = prefix[-1].channel_id
            prev_genre = prefix[-1].genre
            prev_streak = 0
            for p in reversed(prefix):
                if p.genre == prev_genre:
                    prev_streak += 1
                else:
                    break
        else:
            prev_chan = None
            prev_genre = ""
            prev_streak = 0

        initial_state = {
            "score": 0,
            "end_time": left_bound,
            "channel": prev_chan,
            "genre": prev_genre,
            "streak": prev_streak,
            "sequence": [],
            "inside_ids": set()
        }
        
        beam = [initial_state]
        best_score = float('-inf')
        best_seq = []
        
        min_dur = self.context.min_duration
        if min_dur < 1:
            min_dur = 1
            
        diff = right_bound - left_bound
        max_depth = (diff // min_dur) + 1
        if max_depth < 1:
            max_depth = 1
        
        for step in range(max_depth):
            next_beam = []
            
            for state in beam:
                term_score = state["score"]
                
                if len(suffix) > 0:
                    next_chan = suffix[0].channel_id
                    next_gen = suffix[0].genre
                    
                    if state["genre"] == next_gen and state["streak"] + 1 > self.context.max_consecutive_genre:
                        term_score = None
                    elif state["channel"] is not None and state["channel"] != next_chan:
                        term_score -= self.context.switch_penalty
                
                if term_score is not None and term_score > best_score:
                    best_score = term_score
                    best_seq = state["sequence"]

                for item in pool:
                    if item.unique_program_id in state["inside_ids"]:
                        continue
                    if item.start < state["end_time"]:
                        continue
                        
                    if item.genre == state["genre"]:
                        new_streak = state["streak"] + 1
                    else:
                        new_streak = 1
                        
                    if new_streak > self.context.max_consecutive_genre:
                        continue
                        
                    inc = item.fitness
                    if state["channel"] is not None and state["channel"] != item.channel_id:
                        inc -= self.context.switch_penalty
                        
                    bonus = 0
                    if item.signature() in guide_sigs:
                        bonus = 6
                        
                    new_inside_ids = set(state["inside_ids"])
                    new_inside_ids.add(item.unique_program_id)
                    
                    new_sequence = list(state["sequence"])
                    new_sequence.append(item)
                    
                    new_state = {
                        "score": state["score"] + inc + bonus,
                        "end_time": item.end,
                        "channel": item.channel_id,
                        "genre": item.genre,
                        "streak": new_streak,
                        "sequence": new_sequence,
                        "inside_ids": new_inside_ids
                    }
                    next_beam.append(new_state)

            if len(next_beam) == 0:
                break
                
            next_beam.sort(key=lambda x: x["score"], reverse=True)
            beam = next_beam[:self.window_beam_width]

        merged_segments = []
        for p in prefix:
            merged_segments.append(p)
        for p in best_seq:
            merged_segments.append(p)
        for p in suffix:
            merged_segments.append(p)
            
        cand = self.context.solution_from_segments(merged_segments, source="ils_repair")
        is_valid, reason = self.context.validate_schedule(cand.scheduled_programs)
        
        if is_valid:
            return cand
        else:
            return solution
#9
    def intensify_and_polish(self, current: CandidateSolution, guide: Optional[CandidateSolution], stagnation: int) -> CandidateSolution:
        prog_len = len(current.scheduled_programs)
        if prog_len == 0:
            return current
        
        block_size = 1 + (stagnation // 2)
        if block_size < 1:
            block_size = 1
        if block_size > self.max_block_size:
            block_size = self.max_block_size
        if block_size > prog_len:
            block_size = prog_len
            
        weak_idx = self.find_weakest_index(current.scheduled_programs)
        moves = []
        
        first_move = self.get_window(weak_idx, block_size, prog_len)
        moves.append(first_move)
        
        if stagnation >= 3:
            max_start = prog_len - block_size
            if max_start < 0:
                max_start = 0
            rand_start = self.random.randint(0, max_start)
            moves.append((rand_start, rand_start + block_size))

        best_cand = current
        
        trials = moves[:self.neighborhood_trials]
        for start_idx, end_idx in trials:
            cand = self.repair_window(current, start_idx, end_idx, guide)
            if cand.total_score > best_cand.total_score:
                best_cand = cand

        if best_cand.total_score >= current.total_score:
            for round_num in range(self.polish_rounds):
                weakest = self.find_weakest_index(best_cand.scheduled_programs)
                start_idx, end_idx = self.get_window(weakest, 2, len(best_cand.scheduled_programs))
                polished = self.repair_window(best_cand, start_idx, end_idx, guide)
                
                if polished.total_score > best_cand.total_score:
                    best_cand = polished
                else:
                    break
                    
        return best_cand
#2
    def generate_solution(self) -> CandidateSolution:
        beam_solver = BeamSearchScheduler(self.instance_data, beam_width=self.seed_beam_width, verbose=False)
        beam_sol_raw = beam_solver.generate_solution()
        
        dps_solver = SmartTVSchedulerScoreBoost(self.instance_data, top_k=self.catalog_top_k, max_iters=20)
        dps_sol_raw = dps_solver.generate_solution()
        
        beam_segments = []
        for i in beam_sol_raw.scheduled_programs:
            enriched = self.context.enrich_segment(i, "beam")
            beam_segments.append(enriched)
        beam_sol = self.context.solution_from_segments(beam_segments, "beam")
        
        dps_segments = []
        for i in dps_sol_raw.scheduled_programs:
            enriched = self.context.enrich_segment(i, "dps")
            dps_segments.append(enriched)
        dps_sol = self.context.solution_from_segments(dps_segments, "dps")
        
        if beam_sol.total_score >= dps_sol.total_score:
            best_seed = beam_sol
            alt_seed = dps_sol
        else:
            best_seed = dps_sol
            alt_seed = beam_sol

        self.build_catalog([best_seed, alt_seed])
        self.register_elite(best_seed)
        
        current = best_seed.clone()
        best = best_seed.clone()
        stagnation = 0

        for iteration in range(self.max_iterations):
            if stagnation >= 4 and len(self.elite_pool) > 0:
                top_elites = self.elite_pool[:3]
                current = self.random.choice(top_elites).clone()
            
            if iteration % 2 == 1 and len(self.elite_pool) > 0:
                guide = self.elite_pool[0]
            else:
                guide = alt_seed
                
            candidate = self.intensify_and_polish(current, guide, stagnation)
            self.register_elite(candidate)

            if candidate.total_score > best.total_score:
                best = candidate.clone()
                current = candidate.clone()
                stagnation = 0
                continue

            loss = current.total_score - candidate.total_score
            tolerance = self.context.switch_penalty + (stagnation * 2)
            
            if loss <= tolerance and self.random.random() < 0.30:
                current = candidate
                
            stagnation += 1

        best.metadata["initial_score"] = best_seed.total_score
        return best