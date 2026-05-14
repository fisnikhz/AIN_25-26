import math
import random
import time
from copy import deepcopy

import config.simulated_annealing_config as config

from solvers.base_solver import BaseSolver
from models.instance.instance_data import InstanceData
from models.solution.solution import Solution
from operators.replace import replace
from operators.shift_borders import shift_borders, TargetBorder, Mode
from operators.swap import swap


class SimulatedAnnealingSolver(BaseSolver):
    def __init__(
        self,
        solution: Solution,
        t0: float = None,
        tf: float = None,
        alpha: float = None,
        ns: int = None,
        max_shift: int = None,
        max_time: float = None,
        seed: int = None,
    ):
        super().__init__(solution)
        self.t0 = t0 if t0 is not None else getattr(config, "T0", 1000.0)
        self.tf = tf if tf is not None else getattr(config, "TF", 1.0)
        self.alpha = alpha if alpha is not None else getattr(config, "ALPHA", 0.95)
        self.ns = ns if ns is not None else getattr(config, "NS", 100)
        self.max_shift = max_shift if max_shift is not None else getattr(config, "MAX_SHIFT", 10)
        self.max_time = max_time  # optional wall-clock limit in seconds

        # None means no cutoff (plain SA). SA-Cutoff subclass overrides this.
        self.na_cutoff = None

        if seed is not None:
            random.seed(seed)

        self._stats = {
            "accepted_moves": 0,
            "rejected_moves": 0,
            "total_iterations": 0,
            "temperature_steps": 0,
        }

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def solve(self, instance: InstanceData) -> Solution:
        solver_name = self.__class__.__name__
        print(f"\n{'='*60}")
        print(solver_name)
        print(f"{'='*60}")
        print(
            f"T0={self.t0}  Tf={self.tf}  alpha={self.alpha}  "
            f"Ns={self.ns}"
            + (f"  Na={self.na_cutoff}" if self.na_cutoff is not None else "")
        )

        start_time = time.time()

        # Random starting point: perturb the provided initial solution
        current = self._generate_random_solution(instance)
        best = deepcopy(current)
        print(f"Random initial fitness: {current.fitness:.2f}")

        T = self.t0

        while T >= self.tf:
            if self.max_time and (time.time() - start_time) >= self.max_time:
                print(f"[TIMEOUT] Stopping at T={T:.4f} after {self.max_time}s")
                break

            current, accepted, rejected = self._run_inner_loop(current, T, instance)

            self._stats["accepted_moves"] += accepted
            self._stats["rejected_moves"] += rejected
            self._stats["total_iterations"] += accepted + rejected
            self._stats["temperature_steps"] += 1

            if current.fitness > best.fitness:
                print(f"[BEST] T={T:.4f} | {best.fitness:.2f} -> {current.fitness:.2f}")
                best = deepcopy(current)

            T *= self.alpha

        elapsed = time.time() - start_time
        self._print_stats(best.fitness, elapsed)
        return best

    # ------------------------------------------------------------------
    # Inner loop (overridable by subclasses if needed)
    # ------------------------------------------------------------------

    def _run_inner_loop(
        self, current: Solution, T: float, instance: InstanceData
    ):
        accepted = 0
        rejected = 0
        ns = 0

        while ns < self.ns and (self.na_cutoff is None or accepted < self.na_cutoff):
            neighbor = self._mutate(instance, deepcopy(current))

            # ΔF > 0  →  neighbor is worse  →  apply Boltzmann probability
            delta = current.fitness - neighbor.fitness

            if delta <= 0 or random.random() < math.exp(-delta / T):
                current = neighbor
                accepted += 1
            else:
                rejected += 1

            ns += 1

        return current, accepted, rejected

    # ------------------------------------------------------------------
    # Neighbor generation
    # ------------------------------------------------------------------

    def _mutate(self, instance: InstanceData, solution: Solution) -> Solution:
        """Apply one random neighborhood operator (swap / shift / replace)."""
        scheduled = solution.selected.scheduled_programs
        if not scheduled:
            return solution

        r = random.random()
        try:
            if r < 0.4 and len(scheduled) >= 2:
                p1, p2 = random.sample(scheduled, 2)
                return swap(instance, solution, p1, p2)
            elif r < 0.75:
                program = random.choice(scheduled)
                mode = random.choice(list(Mode))
                direction = random.choice(list(TargetBorder))
                shamt = random.randint(1, self.max_shift)
                return shift_borders(instance, solution, program, mode, direction, shamt)
            else:
                return replace(solution, instance)
        except Exception:
            return solution

    # ------------------------------------------------------------------
    # Random initial solution
    # ------------------------------------------------------------------

    def _generate_random_solution(self, instance: InstanceData) -> Solution:
        solution = deepcopy(self.solution)
        n_perturbations = min(max(20, len(solution.selected.scheduled_programs) // 2), 50)

        for _ in range(n_perturbations):
            solution = self._mutate(instance, solution)

        return solution

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _print_stats(self, best_fitness: float, elapsed: float):
        total = self._stats["total_iterations"]
        accepted = self._stats["accepted_moves"]
        rejected = self._stats["rejected_moves"]
        steps = self._stats["temperature_steps"]

        accept_rate = (accepted / total * 100) if total > 0 else 0.0

        print(f"\n{'='*60}")
        print("FINAL STATISTICS")
        print(f"{'='*60}")
        print(f"Best Fitness       : {best_fitness:.2f}")
        print(f"Execution Time     : {elapsed:.2f}s")
        print(f"Temperature Steps  : {steps}")
        print(f"Total Iterations   : {total}")
        print(f"Accepted Moves     : {accepted}  ({accept_rate:.1f}%)")
        print(f"Rejected Moves     : {rejected}")
