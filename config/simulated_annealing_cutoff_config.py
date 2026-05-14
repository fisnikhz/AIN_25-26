T0 = 1000.0     # Initial temperature
TF = 1.0        # Final temperature (stopping condition)
ALPHA = 0.95    # Geometric cooling factor (0 < alpha < 1)
NS = 100        # Maximum neighbor evaluations per temperature level
NA = 30         # Maximum accepted moves per temperature level (cutoff)
MAX_SHIFT = 10  # Maximum shift amount passed to shift_borders operator
