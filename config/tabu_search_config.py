MAX_ITERATIONS = 500
TABU_TENURE = 20
NEIGHBORHOOD_SIZE = 50
MAX_SHIFT = 15
PATIENCE = 200

# Diversification (frequency-penalty mode, pure Tabu)
DIVERSIFICATION_TRIGGER = 80
DIVERSITY_WEIGHT = 5.0
DIVERSIFICATION_DURATION = 20

# Intensification (elite solutions restart, pure Tabu)
ELITE_SIZE = 5
INTENSIFICATION_TRIGGER = 100

# insert_best is O(unselected_count) — skip it on large instances
MAX_UNSELECTED_FOR_INSERT = 500
