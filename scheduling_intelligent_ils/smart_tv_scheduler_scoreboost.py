import json
import sys
from collections import defaultdict

from scheduling_intelligent_ils.common import CandidateSolution
from scheduling_intelligent_ils.common import InstanceContext

NEG_INF = -10**18


def interval_overlap_len(a1, a2, b1, b2):
    return max(0, min(a2, b2) - max(a1, b1))


def preprocess_priority_blocks(priority_blocks):
    for block in priority_blocks:
        block["allowed_set"] = set(block.get("allowed_channels", []))
    priority_blocks.sort(key=lambda item: (item["start"], item["end"]))


def channel_allowed(channel_id, start, end, priority_blocks):
    for block in priority_blocks:
        if block["end"] <= start:
            continue
        if block["start"] >= end:
            break
        if channel_id not in block["allowed_set"]:
            return False
    return True


def compute_bonus(seg_start, seg_end, genre, min_duration, time_prefs):
    total = 0
    for pref in time_prefs:
        if genre != pref["preferred_genre"]:
            continue
        if interval_overlap_len(seg_start, seg_end, pref["start"], pref["end"]) >= min_duration:
            total += pref["bonus"]
    return total


def top2_init():
    return [(NEG_INF, None, None, None, None), (NEG_INF, None, None, None, None)]


def better(a, b):
    if a[0] != b[0]:
        return a[0] > b[0]
    ai = a[3] if a[3] is not None else 10**18
    bi = b[3] if b[3] is not None else 10**18
    return ai < bi


def top2_update(cur, cand):
    a, b = cur[0], cur[1]
    if not better(cand, b):
        return cur
    if better(cand, a):
        return [cand, a]
    return [a, cand]


def best_excluding_genre(top2_list, bad_genre):
    a, b = top2_list[0], top2_list[1]
    if a[0] > NEG_INF / 2 and a[1] != bad_genre:
        return a
    if b[0] > NEG_INF / 2 and b[1] != bad_genre:
        return b
    return (NEG_INF, None, None, None, None)


def best_matching_genre(top2_list, want_genre):
    a, b = top2_list[0], top2_list[1]
    if a[0] > NEG_INF / 2 and a[1] == want_genre:
        return a
    if b[0] > NEG_INF / 2 and b[1] == want_genre:
        return b
    return (NEG_INF, None, None, None, None)


def solve_dp(segments, max_consecutive_genre, switch_penalty):
    segment_count = len(segments)
    if segment_count == 0:
        return [], 0

    segments = sorted(
        segments,
        key=lambda item: (item["seg_start"], item["seg_end"], item["channel_id"], item["unique_program_id"]),
    )
    by_end = sorted(range(segment_count), key=lambda idx: segments[idx]["seg_end"])
    seg_value = [item["score"] + item["bonus"] - item["cut_penalty"] for item in segments]

    dp = [defaultdict(lambda: NEG_INF) for _ in range(segment_count)]
    parent = {}

    global_best = [top2_init() for _ in range(max_consecutive_genre + 1)]
    global_best_anyk = top2_init()
    per_channel_best = [defaultdict(top2_init) for _ in range(max_consecutive_genre + 1)]
    per_channel_best_anyk = defaultdict(top2_init)

    for idx in range(segment_count):
        dp[idx][1] = seg_value[idx]
        parent[(idx, 1)] = None

    end_ptr = 0

    for idx in range(segment_count):
        current = segments[idx]
        start_i = current["seg_start"]
        genre_i = current["genre"]
        channel_i = current["channel_id"]

        while end_ptr < segment_count:
            prev_idx = by_end[end_ptr]
            if segments[prev_idx]["seg_end"] > start_i:
                break

            previous = segments[prev_idx]
            for k_prev, value_prev in dp[prev_idx].items():
                if value_prev <= NEG_INF / 2:
                    continue
                candidate = (value_prev, previous["genre"], previous["channel_id"], prev_idx, k_prev)
                global_best[k_prev] = top2_update(global_best[k_prev], candidate)
                per_channel_best[k_prev][previous["channel_id"]] = top2_update(
                    per_channel_best[k_prev][previous["channel_id"]],
                    candidate,
                )
                global_best_anyk = top2_update(global_best_anyk, candidate)
                per_channel_best_anyk[previous["channel_id"]] = top2_update(
                    per_channel_best_anyk[previous["channel_id"]],
                    candidate,
                )

            end_ptr += 1

        best_same_ch = best_excluding_genre(per_channel_best_anyk[channel_i], genre_i)
        best_same_score = best_same_ch[0]

        best_global = best_excluding_genre(global_best_anyk, genre_i)
        best_global_score = best_global[0] - switch_penalty if best_global[0] > NEG_INF / 2 else NEG_INF

        if best_same_score > NEG_INF / 2 or best_global_score > NEG_INF / 2:
            if best_same_score >= best_global_score:
                pred = best_same_ch
                pred_score = best_same_score
            else:
                pred = best_global
                pred_score = best_global_score

            candidate_score = pred_score + seg_value[idx]
            if candidate_score > dp[idx][1]:
                dp[idx][1] = candidate_score
                parent[(idx, 1)] = (pred[3], pred[4])

        for k_prev in range(1, max_consecutive_genre):
            k_new = k_prev + 1
            best_same = best_matching_genre(per_channel_best[k_prev][channel_i], genre_i)
            same_score = best_same[0]

            best_global = best_matching_genre(global_best[k_prev], genre_i)
            diff_score = best_global[0] - switch_penalty if best_global[0] > NEG_INF / 2 else NEG_INF

            if same_score <= NEG_INF / 2 and diff_score <= NEG_INF / 2:
                continue

            if same_score >= diff_score:
                pred = best_same
                pred_score = same_score
            else:
                pred = best_global
                pred_score = diff_score

            candidate_score = pred_score + seg_value[idx]
            if candidate_score > dp[idx][k_new]:
                dp[idx][k_new] = candidate_score
                parent[(idx, k_new)] = (pred[3], pred[4])

    best_score = NEG_INF
    best_state = None
    for idx in range(segment_count):
        for streak, score in dp[idx].items():
            if score > best_score:
                best_score = score
                best_state = (idx, streak)

    chosen_indices = []
    current_state = best_state
    while current_state is not None:
        idx, streak = current_state
        chosen_indices.append(idx)
        current_state = parent.get(current_state)
    chosen_indices.reverse()

    schedule = [segments[idx] for idx in chosen_indices]

    total = 0
    previous = None
    for item in schedule:
        total += item["score"] + item["bonus"] - item["cut_penalty"]
        if previous and previous["channel_id"] != item["channel_id"]:
            total -= switch_penalty
        previous = item

    return schedule, total


def improve_unique_programs(all_segments, max_consecutive_genre, switch_penalty, max_iters=15):
    disabled = set()

    def seg_key(item):
        return (
            item["unique_program_id"],
            item["seg_start"],
            item["seg_end"],
            item["channel_id"],
        )

    best_schedule = []
    best_score = NEG_INF

    for _ in range(max_iters):
        active_segments = [item for item in all_segments if seg_key(item) not in disabled]
        schedule, score = solve_dp(active_segments, max_consecutive_genre, switch_penalty)

        if score > best_score:
            best_score = score
            best_schedule = schedule

        occurrences = defaultdict(list)
        for idx, item in enumerate(schedule):
            occurrences[item["unique_program_id"]].append((idx, item))

        duplicated = [key for key, entries in occurrences.items() if len(entries) > 1]
        if not duplicated:
            return schedule, score

        for unique_program_id in sorted(duplicated):
            entries = occurrences[unique_program_id]

            def marginal(position, item):
                base = item["score"] + item["bonus"] - item["cut_penalty"]
                penalty = 0
                if position > 0 and schedule[position - 1]["channel_id"] != item["channel_id"]:
                    penalty += switch_penalty
                if position < len(schedule) - 1 and schedule[position + 1]["channel_id"] != item["channel_id"]:
                    penalty += switch_penalty
                return base - penalty

            ranked = sorted(
                [(marginal(position, item), position, item) for (position, item) in entries],
                key=lambda row: (-row[0], row[1], seg_key(row[2])),
            )

            for _, _, item in ranked[1:]:
                disabled.add(seg_key(item))

    return best_schedule, best_score


def build_segments(data):
    opening = data["opening_time"]
    closing = data["closing_time"]
    min_duration = data["min_duration"]
    termination_penalty = data["termination_penalty"]

    priority_blocks = data.get("priority_blocks", [])
    time_prefs = data.get("time_preferences", [])
    preprocess_priority_blocks(priority_blocks)

    segments = []
    seen = set()

    interesting_times = {opening, closing}
    for pref in time_prefs:
        interesting_times.add(pref["start"])
        interesting_times.add(pref["end"])
    for block in priority_blocks:
        interesting_times.add(block["start"])
        interesting_times.add(block["end"])
    interesting_times = sorted(time for time in interesting_times if opening <= time <= closing)

    def add_segment(base, seg_start, seg_end):
        if seg_start < opening or seg_end > closing or seg_end <= seg_start:
            return

        program_length = base["end"] - base["start"]
        segment_length = seg_end - seg_start

        if program_length < min_duration:
            if seg_start != base["start"] or seg_end != base["end"]:
                return
        elif segment_length < min_duration:
            return

        if not channel_allowed(base["channel_id"], seg_start, seg_end, priority_blocks):
            return

        key = (base["unique_program_id"], seg_start, seg_end, base["channel_id"])
        if key in seen:
            return
        seen.add(key)

        cut_penalty = 0
        if seg_start > base["start"]:
            cut_penalty += termination_penalty
        if seg_end < base["end"]:
            cut_penalty += termination_penalty

        bonus = compute_bonus(seg_start, seg_end, base["genre"], min_duration, time_prefs)

        segments.append(
            {
                "program_id": base["program_id"],
                "unique_program_id": base["unique_program_id"],
                "channel_id": base["channel_id"],
                "prog_start": base["start"],
                "prog_end": base["end"],
                "seg_start": seg_start,
                "seg_end": seg_end,
                "genre": base["genre"],
                "score": base["score"],
                "bonus": bonus,
                "cut_penalty": cut_penalty,
            }
        )

    for channel in data["channels"]:
        channel_id = channel["channel_id"]
        for program in channel["programs"]:
            if program["end"] <= opening or program["start"] >= closing:
                continue

            full_start = max(program["start"], opening)
            full_end = min(program["end"], closing)
            base = {
                "program_id": program["program_id"],
                "unique_program_id": program["unique_program_id"],
                "channel_id": channel_id,
                "start": full_start,
                "end": full_end,
                "genre": program["genre"],
                "score": program["score"],
            }

            add_segment(base, full_start, full_end)

            if full_end - full_start >= min_duration:
                add_segment(base, full_start, full_start + min_duration)
                add_segment(base, full_end - min_duration, full_end)

            for pref in time_prefs:
                if program["genre"] != pref["preferred_genre"]:
                    continue
                seg_start = max(full_start, pref["start"])
                seg_end = seg_start + min_duration
                if seg_end <= full_end:
                    add_segment(base, seg_start, seg_end)

            if full_end - full_start >= min_duration:
                for time in interesting_times:
                    if full_start <= time <= full_end - min_duration:
                        add_segment(base, time, time + min_duration)
                    if full_start + min_duration <= time <= full_end:
                        add_segment(base, time - min_duration, time)

    return segments


def keep_top_k_per_program(segments, top_k=8):
    buckets = defaultdict(list)
    for item in segments:
        value = item["score"] + item["bonus"] - item["cut_penalty"]
        buckets[item["unique_program_id"]].append((value, item))

    pruned = []
    for _, bucket in buckets.items():
        bucket.sort(key=lambda row: (-row[0], row[1]["seg_start"], row[1]["seg_end"], row[1]["channel_id"]))
        for _, item in bucket[:top_k]:
            pruned.append(item)

    return pruned


def instance_to_data(instance):
    data = {
        "opening_time": instance.opening_time,
        "closing_time": instance.closing_time,
        "min_duration": instance.min_duration,
        "max_consecutive_genre": instance.max_consecutive_genre,
        "switch_penalty": instance.switch_penalty,
        "termination_penalty": instance.termination_penalty,
        "priority_blocks": [],
        "time_preferences": [],
        "channels": [],
    }

    for block in getattr(instance, "priority_blocks", []):
        data["priority_blocks"].append(
            {
                "start": block.start,
                "end": block.end,
                "allowed_channels": list(block.allowed_channels),
            }
        )

    for pref in getattr(instance, "time_preferences", []):
        data["time_preferences"].append(
            {
                "start": pref.start,
                "end": pref.end,
                "preferred_genre": pref.preferred_genre,
                "bonus": pref.bonus,
            }
        )

    for channel in instance.channels:
        channel_payload = {"channel_id": channel.channel_id, "programs": []}
        for program in channel.programs:
            channel_payload["programs"].append(
                {
                    "program_id": program.program_id,
                    "unique_program_id": program.unique_id,
                    "start": program.start,
                    "end": program.end,
                    "genre": program.genre,
                    "score": program.score,
                }
            )
        data["channels"].append(channel_payload)

    return data


class SmartTVSchedulerScoreBoost:
    def __init__(self, instance_data, top_k=8, max_iters=40, verbose=False):
        self.instance_data = instance_data
        self.top_k = top_k
        self.max_iters = max_iters
        self.verbose = verbose
        self.context = InstanceContext(instance_data)
        self.last_candidate_segments = []

    def generate_raw_schedule(self):
        data = instance_to_data(self.instance_data)
        max_consecutive_genre = data["max_consecutive_genre"]
        switch_penalty = data["switch_penalty"]

        segments = build_segments(data)
        if not segments:
            return [], 0

        segments = keep_top_k_per_program(segments, top_k=self.top_k)
        self.last_candidate_segments = list(segments)
        schedule, final_score = improve_unique_programs(
            segments,
            max_consecutive_genre=max_consecutive_genre,
            switch_penalty=switch_penalty,
            max_iters=self.max_iters,
        )
        return schedule, int(final_score)

    def generate_solution(self):
        raw_schedule, final_score = self.generate_raw_schedule()
        scheduled_programs = []

        for item in raw_schedule:
            channel_id, program = self.context.unique_program_lookup[item["unique_program_id"]]
            scheduled_programs.append(
                self.context.create_segment(
                    channel_id=channel_id,
                    program=program,
                    start=item["seg_start"],
                    end=item["seg_end"],
                    source="dps_scoreboost",
                )
            )

        solution = CandidateSolution(
            scheduled_programs=scheduled_programs,
            total_score=self.context.evaluate_segments(scheduled_programs),
            source="dps_scoreboost",
        )

        if self.verbose:
            print(f"[DP-S] Final score: {final_score}")
            print(f"[DP-S] Normalized score: {solution.total_score}")
            print(f"[DP-S] Schedule length: {len(solution.scheduled_programs)}")

        return solution


def run_from_json_dict(data, top_k=8, max_iters=40):
    max_consecutive_genre = data["max_consecutive_genre"]
    switch_penalty = data["switch_penalty"]

    segments = build_segments(data)
    if not segments:
        return {"scheduled_programs": [], "total_score": 0}

    segments = keep_top_k_per_program(segments, top_k=top_k)
    schedule, final_score = improve_unique_programs(
        segments,
        max_consecutive_genre=max_consecutive_genre,
        switch_penalty=switch_penalty,
        max_iters=max_iters,
    )

    return {
        "scheduled_programs": [
            {
                "program_id": item["program_id"],
                "channel_id": item["channel_id"],
                "start": item["seg_start"],
                "end": item["seg_end"],
            }
            for item in schedule
        ],
        "total_score": int(final_score),
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python smart_tv_scheduler_scoreboost.py input.json output.json")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    with open(input_file, "r", encoding="utf-8") as file:
        data = json.load(file)

    result = run_from_json_dict(data, top_k=8, max_iters=40)

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=2)

    print("Schedule written to", output_file)
    print("Total score:", result["total_score"])


if __name__ == "__main__":
    main()
