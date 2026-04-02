# Detyra në Algoritmet e Avancuara
## Universiteti i Prishtinës - FIEK

---

# IMPLEMENTIMET AKTUALE

## 1. Hill Climbing me Random Restarts - `run_hill_climbing_restarts.py`

### Karakteristikat kryesore:
- **Random Seed Initialization**: Përdor `int(time.time() * 1000)` për randomness të vërtetë
- **Flexible Input**: Mund të merr instance file si argument ose zgjedh interaktivisht  
- **Validation Checks**: Kontrollon constraint violations pas ekzekutimit
- **Output Management**: Ruaj rezultatet në `data/solutions/hillclimbing_restarts/`

### Përdorimi:
```bash
# Me argument (direkt)
python run_hill_climbing_restarts.py data/input/australia_iptv.json

# Interaktiv (zgjedh file)  
python run_hill_climbing_restarts.py
```

### Struktura e main():
```python
def main():
    # 1. Random Seed Initialization 
    seed = int(time.time() * 1000) % (2**32)
    random.seed(seed)
    
    # 2. File Selection (arg ose interactive)
    if len(sys.argv) > 1:
        instance_file = sys.argv[1]  # Direct file
    else:
        instance_file = select_file()  # Interactive
    
    # 3. Parse Instance + Initial Solution
    parser = InstanceParser(instance_file)
    instance = parser.parse()
    
    # 4. Build Solution Object
    solution = Solution(evaluator, selected, unselected_ids)
    
    # 5. Hill Climbing Execution
    solver = HillClimbingRestartsSolver(
        solution=solution,
        instance=instance,
        num_restarts=config.NUM_RESTARTS,
        insertion_interval=config.INSERTION_INTERVAL,
        max_iterations=config.MAX_ITERATIONS
    )
    
    # 6. Final Validation & Save
    best_solution = solver.solve()
    validate_and_save(best_solution)
```

---

## 2. Hill Climbing Restarts Solver - `solvers/hill_climbing_restarts_solver.py`

### Karakteristikat kryesore:
- **HashMap Data Structures**: O(1) program lookups me `self.program_map`
- **True Random Restarts**: Çdo restart bën perturbim të ndryshëm nga global best
- **Insertion Integration**: Insert operator aktivizohet çdo N iteracione
- **Multi-Operator Search**: Combine shift, swap, replace, insert operators

### Algoritmi Core:
```python
def solve(self):
    global_best = deepcopy(self.initial_solution)
    
    for restart in range(self.num_restarts):
        # Restart Strategy
        if restart == 0:
            current = deepcopy(self.initial_solution)
        else:
            current = self._perturb_solution(global_best)  # Perturb from global best
        
        # Hill Climbing Loop
        for iteration in range(self.max_iterations):
            # Insertion Operator (çdo N iteracione)
            if iteration % self.insertion_interval == 0 and iteration > 0:
                current = insert_best(current, self.instance)
            
            # Find Improving Neighbor
            neighbor = self._find_improving_neighbor()
            if neighbor is None:
                break  # Local optimum
            
            current = neighbor
            
        # Update Global Best
        if current.fitness > global_best.fitness:
            global_best = deepcopy(current)
    
    return global_best
```

### Perturbation Strategy:
- **Restart 1**: Përdor initial solution
- **Restart 2+**: Perturb nga global best (jo nga initial)
- **Operations**: Random mix i replace, shift, swap
- **Intensity**: 5-15 operacione per perturbation

---

## 3. Insert Operator - `operators/insert.py`

### Dy Versione të Implementuara:

#### `insert()` - Version Standard:
```python
def insert(solution, instance):
    # 1. Gjej gaps në schedule
    gaps = _find_gaps(scheduled, instance)
    
    # 2. Për çdo program unselected
    for program_id in unselected_ids:
        # 3. Kontrollo nëse fitet në gap
        if duration <= gap_duration:
            # 4. Validates constraints:
            #    - Genre limit (max consecutive)
            #    - No overlap with existing programs  
            #    - Min duration requirement
            #    - Time bounds (opening/closing time)
            
            # 5. Insert dhe return
            return new_solution
```

#### `insert_best()` - Version Optimized:
```python
def insert_best(solution, instance):
    # 1. Event-based gap detection (më i saktë)
    gaps = _find_gaps_event_based(scheduled, instance)
    
    # 2. Try ALL possible insertions
    candidates = []
    for gap in gaps:
        for program in unselected:
            if fits_in_gap_with_constraints(program, gap):
                candidates.append((program, gap, fitness_improvement))
    
    # 3. Zgjedh BEST insertion (highest fitness gain)
    best_candidate = max(candidates, key=lambda x: x[2])
    return apply_insertion(best_candidate)
```

### Gap Detection Algorithm:
```python
def _find_gaps_event_based(scheduled, instance):
    # Event-based approach për multi-channel schedules
    events = []
    for program in scheduled:
        events.append((program.start, 'start', program.channel_id))
        events.append((program.end, 'end', program.channel_id))
    
    events.sort()  # Sort by time
    
    # Track occupancy per channel
    channel_occupancy = {}
    gaps = []
    
    for time, event_type, channel_id in events:
        if event_type == 'start':
            channel_occupancy[channel_id] = time
        else:  # 'end'
            if channel_id in channel_occupancy:
                del channel_occupancy[channel_id]
        
        # Find free channels at this time
        for ch_id in range(instance.channels_count):
            if ch_id not in channel_occupancy:
                gaps.append((time, next_occupied_time, ch_id))
    
    return gaps
```

### Constraint Validation:
```python
def _validate_constraints(program, start_time, channel_id, instance, scheduled):
    # 1. Genre Limit Check
    if _violates_genre_limit(program, start_time, channel_id, scheduled, instance):
        return False
    
    # 2. Overlap Check (same channel)  
    if _has_overlap(program, start_time, channel_id, scheduled):
        return False
        
    # 3. Min Duration Check
    if (program.original_end - program.original_start) < instance.min_duration:
        return False
        
    # 4. Time Bounds Check
    if start_time < instance.opening_time or end_time > instance.closing_time:
        return False
        
    # 5. Original Time Window Check
    original_start = program.original_start  
    original_end = program.original_end
    if not (original_start <= start_time <= end_time <= original_end):
        return False
    
    return True
```

---

## PËRMIRËSIMET E IMPLEMENTUARA:

### 1. **Crash Prevention**
- Added `None` checks në shift_borders calls:
```python
neighbor = shift_borders(instance, solution, program, mode, direction, shamt)
if neighbor is not None and neighbor.fitness >= current_fitness:
    return neighbor
```

### 2. **True Randomness**  
- Timestamp-based seeds: `random.seed(int(time.time() * 1000))`
- Perturbation from global best (jo nga initial solution)

### 3. **Validation Integration**
- Program Continuity checks
- Constraint violation detection
- Score discrepancy monitoring

### 4. **Performance Optimization**
- HashMap data structures për O(1) lookups  
- Event-based gap detection
- Best-first insertion strategy

---

# PSEUDOKODI

## 1. Hill Climbing me Random Restarts

```
Algorithm: Hill_Climbing_Random_Restarts

Input:
    initial_solution      - zgjidhja fillestare
    num_restarts         - numri i restarts (PARAMETËR, default=10)
    insertion_interval   - insertion çdo N iteracione (PARAMETËR, default=100)
    max_iterations       - max iteracione per restart

Output:
    global_best          - zgjidhja më e mirë

BEGIN
    global_best = initial_solution
    
    FOR restart = 1 TO num_restarts DO
        
        IF restart == 1 THEN
            current = initial_solution
        ELSE
            current = Perturb(initial_solution)   // Perturbim random
        END IF
        
        iteration = 0
        improved = TRUE
        
        WHILE improved AND iteration < max_iterations DO
            iteration = iteration + 1
            
            // INSERTION OPERATOR çdo N iteracione
            IF iteration MOD insertion_interval == 0 THEN
                current = Insert_Operator(current)
            END IF
            
            // HILL CLIMBING: gjej çfarëdo përmirësim
            neighbor = Find_Improving_Neighbor(current)
            
            IF fitness(neighbor) > fitness(current) THEN
                current = neighbor
            ELSE IF fitness(neighbor) == fitness(current) THEN
                current = neighbor    // Pranon edhe lëvizje neutrale
            ELSE
                improved = FALSE      // Optimum lokal
            END IF
            
        END WHILE
        
        // Ruaj nëse është më e mirë
        IF fitness(current) > fitness(global_best) THEN
            global_best = current
        END IF
        
    END FOR
    
    RETURN global_best
END
```

---

## 2. Insertion Operator (ku ka vend)

```
Algorithm: Insert_Operator

Input:
    solution    - zgjidhja aktuale
    instance    - të dhënat e problemit

Output:
    new_solution - zgjidhja me programin e insertuar

BEGIN
    scheduled = Sort_By_Time(solution.selected)
    unselected = solution.unselected_ids
    
    // Hapi 1: Gjej GAPS (hapësirat) në schedule
    gaps = Find_Gaps(scheduled, instance)
    
    // Hapi 2: Për çdo gap, provo të insertosh program
    FOR EACH (gap_start, gap_end) IN gaps DO
        
        FOR EACH program_id IN unselected DO
            program = Get_Program(program_id)
            duration = program.end - program.start
            gap_duration = gap_end - gap_start
            
            // Hapi 3: Kontrollo nëse FITET në gap
            IF duration <= gap_duration THEN
                
                // Hapi 4: Kontrollo priority blocks
                IF Respects_Priority_Blocks(gap_start, duration, channel_id) THEN
                    
                    // Hapi 5: INSERTO!
                    new_program = Create_Scheduled_Program(
                        program_id = program.id,
                        channel_id = channel_id,
                        start = gap_start,
                        end = gap_start + duration
                    )
                    
                    solution.selected.ADD(new_program)
                    solution.unselected.REMOVE(program_id)
                    
                    RETURN solution
                END IF
            END IF
        END FOR
    END FOR
    
    RETURN solution   // Asnjë insertion i mundshëm
END


Algorithm: Find_Gaps

Input:
    scheduled   - lista e programeve të zgjedhura (sorted by time)
    instance    - të dhënat e problemit

Output:
    gaps        - lista e hapësirave (start, end)

BEGIN
    gaps = []
    
    // Gap në FILLIM (para programit të parë)
    IF scheduled[0].start > instance.opening_time THEN
        gaps.ADD( (instance.opening_time, scheduled[0].start) )
    END IF
    
    // Gaps MIDIS programeve
    FOR i = 0 TO length(scheduled) - 2 DO
        end_current = scheduled[i].end
        start_next = scheduled[i+1].start
        
        IF start_next > end_current THEN
            gaps.ADD( (end_current, start_next) )
        END IF
    END FOR
    
    // Gap në FUND (pas programit të fundit)
    IF scheduled[last].end < instance.closing_time THEN
        gaps.ADD( (scheduled[last].end, instance.closing_time) )
    END IF
    
    RETURN gaps
END
```

---

## Vizualizimi i Insertion

```
Schedule aktual:
|--Prog1--|         |--Prog2--|         |--Prog3--|
600      660       720       780       840       900
          ↑ GAP ↑             ↑ GAP ↑

gaps = [(660, 720), (780, 840)]

Program unselected: duration = 50 min

Kontrollo gap (660, 720):
  - gap_duration = 720 - 660 = 60 min
  - program_duration = 50 min
  - 50 <= 60 ✓ FITET!
  
Rezultat:
|--Prog1--|--NEW--|--|--Prog2--|         |--Prog3--|
600      660     710 720       780       840       900
```

---

# SI TË EKZEKUTOHET

## Hapi 1: Hap terminalin
```bash
cd "C:\Users\PC\Desktop\Algoritmet e inspiruara ne natyre\AIN_25-26"
```

## Hapi 2: Ekzekuto
```bash
python run_hill_climbing_restarts.py
```

## Hapi 3: Zgjidh instance dhe zgjidhjen fillestare
```
=== Zgjidh Instance File ===
1. croatia_tv_input.json
2. germany_tv_input.json
3. kosovo_tv_input.json
Zgjidh numrin: 3

=== Zgjidh Zgjidhjen Fillestare ===
1. kosovo_tv_output_beamsearchscheduler_2587.json
Zgjidh numrin: 1
```

---

# KONFIGURIMI - `config/config.py`

```python
# Performance Settings
MAX_ITERATIONS = 500        # Max iteracione per restart
MAX_SHIFT = 10             # Max shift amount për shift_borders

# Hill Climbing me Random Restarts parameters  
NUM_RESTARTS = 10          # Numri i random restarts (10 për diversitet)
INSERTION_INTERVAL = 50    # Insertion çdo N iteracione (50 për më shumë insertion)
```

### Rekomandime për Parameters:

| Parameter | Rekomandimi | Arsyetimi |
|-----------|-------------|-----------|
| `NUM_RESTARTS` | 10 | Balance midis cilësisë dhe kohës së ekzekutimit |
| `INSERTION_INTERVAL` | 50 | Më shumë insertion = më shumë mundësi për përmirësim |
| `MAX_ITERATIONS` | 500 | Mjaftueshëm për konvergjencë në optimum lokal |

---

# TROUBLESHOOTING

## Problem 1: Crash në shift_borders
**Error**: `TypeError: bad operand type for abs(): 'NoneType'`
**Fix**: Added None checks në hill climbing solver:
```python
if neighbor is not None and neighbor.fitness >= current_fitness:
    return neighbor
```

## Problem 2: Program Continuity Violated
**Error**: Programs scheduled outside original time window
**Fix**: Updated insert operator të përdorë original program times:
```python
# Use original times, not gap times
start_time = program.original_start  
end_time = program.original_end
```

## Problem 3: Same Results në Multiple Runs  
**Error**: Lack of true randomness
**Fix**: Timestamp-based seed initialization:
```python
seed = int(time.time() * 1000) % (2**32)
random.seed(seed)
```

## Problem 4: Score Discrepancy (Terminal vs Validator)
**Potential causes**:
- Different constraint interpretation
- Floating point precision issues  
- Program overlap calculation differences

---

# SHEMBULL OUTPUT

```
============================================================
HILL CLIMBING ME RANDOM RESTARTS
============================================================

Zgjidhja fillestare: 2587
Random Restarts: 10
Insertion interval: çdo 100 iteracione

--- RESTART 1/10 ---
Fillimi: 2587
  [Iter 100] INSERT: 2587 -> 2602
  [Iter 150] Përmirësim: +5.0 -> 2607
Fundi: 2640 (pas 280 iteracioneve)
*** GLOBAL BEST I RI: 2640 ***

--- RESTART 2/10 ---
Fillimi: 2520
Fundi: 2610 (pas 200 iteracioneve)

...

============================================================
STATISTIKA FINALE
============================================================
Best Fitness: 2720
Total Iterations: 2800
Improvements: 127
Insertions: 15
Best per Restart: [2640, 2610, 2680, 2720, ...]
```

---

# STRUKTURA E FILE-VE

```
AIN_25-26/
├── config/
│   └── config.py                        # Parametrat
│
├── solvers/
│   └── hill_climbing_restarts_solver.py # Algoritmi kryesor
│
├── operators/
│   └── insert.py                        # INSERT operator
│
├── data/
│   ├── input/                           # Instance files
│   └── solutions/
│       └── hillclimbing_restarts/       # Output
│
└── run_hill_climbing_restarts.py        # Script për ekzekutim
```

---

# PËRDORIMI SI MODUL

```python
from solvers.hill_climbing_restarts_solver import HillClimbingRestartsSolver

solver = HillClimbingRestartsSolver(
    solution=initial_solution,
    instance=instance,
    num_restarts=10,         # PARAMETËR: Random restarts
    insertion_interval=100,  # PARAMETËR: Insertion çdo N iter
    max_iterations=500
)

best_solution = solver.solve()
print(f"Best fitness: {best_solution.fitness}")
```

---

# TESTING & VALIDATION

## Online Validator
**URL**: https://tv-programms-validator.netlify.app/

### Përdorimi:
1. Run algorithm dhe generate output file
2. Upload file në validator  
3. Check për constraint violations
4. Compare score me terminal output

## Quick Test Script
```bash
# Test me reduced iterations për debugging
python quick_test.py
```

## Test Files të Disponueshëm:
```
data/input/
├── australia_iptv.json      # Large instance (499 channels)
├── china_pw.json           # Medium instance  
├── croatia_tv_input.json   # Small instance
├── germany_tv_input.json   # Medium instance
└── kosovo_tv_input.json    # Small instance
```

### Expected Performance:
| Instance | Channels | Programs | Execution Time | Expected Score Range |
|----------|----------|----------|----------------|---------------------|
| kosovo | ~50 | ~1000 | 30-60s | 2500-3000 |
| croatia | ~100 | ~2000 | 60-120s | 5000-7000 |
| australia | 499 | ~10000 | 300-600s | 15000-25000 |

---

# VERSION HISTORY

## v2.1 - April 2026
- ✅ Fixed shift_borders crash issue
- ✅ Added comprehensive constraint validation
- ✅ Improved gap detection algorithm  
- ✅ Enhanced randomness with timestamp seeds
- ✅ Added None checks throughout codebase

## v2.0 - March 2026  
- ✅ Implemented insert_best() optimized version
- ✅ Added event-based gap detection
- ✅ Fixed Program Continuity violations
- ✅ Added comprehensive debugging output

## v1.0 - Initial Implementation
- ✅ Basic hill climbing with random restarts
- ✅ Simple insertion operator
- ✅ HashMap data structures
- ✅ Basic gap detection

---
