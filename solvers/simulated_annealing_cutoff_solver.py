
import config.simulated_annealing_cutoff_config as cutoff_config

from solvers.simulated_annealing_solver import SimulatedAnnealingSolver
from models.solution.solution import Solution


class SimulatedAnnealingCutoffSolver(SimulatedAnnealingSolver):
    def __init__(
        self,
        solution: Solution,
        t0: float = None,
        tf: float = None,
        alpha: float = None,
        ns: int = None,
        na: int = None,
        max_shift: int = None,
        max_time: float = None,
        seed: int = None,
    ):
        # Resolve SA base parameters from the cutoff config when not provided
        super().__init__(
            solution=solution,
            t0=t0 if t0 is not None else getattr(cutoff_config, "T0", 1000.0),
            tf=tf if tf is not None else getattr(cutoff_config, "TF", 1.0),
            alpha=alpha if alpha is not None else getattr(cutoff_config, "ALPHA", 0.95),
            ns=ns if ns is not None else getattr(cutoff_config, "NS", 100),
            max_shift=max_shift if max_shift is not None else getattr(cutoff_config, "MAX_SHIFT", 10),
            max_time=max_time,
            seed=seed,
        )

        # Na cutoff: activates the early-stop condition inside _run_inner_loop
        self.na_cutoff = na if na is not None else getattr(cutoff_config, "NA", 30)
