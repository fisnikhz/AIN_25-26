"""
Hill Climbing Solver me Random Restarts dhe Insertion Operator.

Detyra:
- Hill Climbing me random restarts (parametër) (-5 pikë)
- Insertion operator çdo N iteracione ku ka vend (-5 pikë)
- HashMap data structures
"""

import random
from copy import deepcopy
from typing import Dict, List, Tuple, Optional

from solvers.base_solver import BaseSolver
from models.instance.instance_data import InstanceData
from models.solution.solution import Solution
from models.solution.schedule import Schedule
from models.solution.scheduled_program import ScheduledProgram
from operators.replace import replace
from operators.shift_borders import shift_borders, TargetBorder, Mode
from operators.swap import swap
from operators.insert import insert, insert_best
import config.hill_climbing_restarts_config as config


class HillClimbingRestartsSolver(BaseSolver):
    """
    Hill Climbing me Random Restarts:
    - 10 Random Restarts (konfigurueshëm)
    - Insertion Operator çdo N iteracione
    - HashMap për lookups O(1)
    
    Hill Climbing pranon ÇFARËDO përmirësim (first improvement)
    """
    
    def __init__(self, solution: Solution,
                 instance: InstanceData,
                 num_restarts: int = 10,
                 insertion_interval: int = 100,
                 max_iterations: int = None):
        super().__init__(solution)
        self.instance = instance
        self.initial_solution = deepcopy(solution)  # Ruaj zgjidhjen fillestare
        self.num_restarts = num_restarts
        self.insertion_interval = insertion_interval
        self.max_iterations = max_iterations or config.MAX_ITERATIONS
        
        # HashMap për program lookup O(1)
        self.program_map: Dict[Tuple[int, str], object] = {}
        self._build_program_map()
        
        # Statistika
        self.stats = {
            'total_iterations': 0,
            'improvements': 0,
            'insertions': 0,
            'best_per_restart': []
        }
    
    def _build_program_map(self):
        """Ndërto HashMap për O(1) lookup."""
        for channel in self.instance.channels:
            for program in channel.programs:
                self.program_map[(channel.channel_id, program.program_id)] = program
    
    def solve(self) -> Solution:
        """
        Ekzekuto Hill Climbing me Random Restarts.
        """
        print("\n" + "="*60)
        print("HILL CLIMBING ME RANDOM RESTARTS")
        print("="*60)
        
        global_best = deepcopy(self.initial_solution)
        global_best_fitness = self.initial_solution.fitness
        
        print(f"Zgjidhja fillestare: {global_best_fitness}")
        print(f"Random Restarts: {self.num_restarts}")
        print(f"Insertion interval: çdo {self.insertion_interval} iteracione")
        
        for restart in range(self.num_restarts):
            print(f"\n--- RESTART {restart + 1}/{self.num_restarts} ---")
            
            # Për restart-in e parë, përdor zgjidhjen origjinale
            # Për të tjerat, bëj perturbim RANDOM nga zgjidhja AKTUALE më e mirë
            if restart == 0:
                self.solution = deepcopy(self.initial_solution)
            else:
                # RANDOMNESS: Bëj perturbim nga GLOBAL BEST, jo nga fillestarja
                self.solution = self._perturb_solution(global_best)
            
            start_fitness = self.solution.fitness
            print(f"Fillimi: {start_fitness}")
            
            # Hill Climbing loop
            iteration = 0
            improved = True
            
            while improved and iteration < self.max_iterations:
                iteration += 1
                self.stats['total_iterations'] += 1
                
                # Insertion operator çdo N iteracione (PARA restart)
                if iteration % self.insertion_interval == 0:
                    old_fitness = self.solution.fitness
                    new_solution = insert_best(self.solution, self.instance)
                    if new_solution.fitness > old_fitness:
                        self.solution = new_solution
                        self.stats['insertions'] += 1
                        print(f"  [Iter {iteration}] INSERT: {old_fitness} -> {self.solution.fitness}")
                
                # Hill Climbing: Gjej ÇFARËDO përmirësim (first improvement)
                neighbor = self._find_improving_neighbor()
                
                if neighbor is not None and neighbor.fitness > self.solution.fitness:
                    improvement = neighbor.fitness - self.solution.fitness
                    self.solution = neighbor
                    self.stats['improvements'] += 1
                    
                    if iteration % 50 == 0:
                        print(f"  [Iter {iteration}] Përmirësim: +{improvement:.1f} -> {self.solution.fitness}")
                elif neighbor is not None and neighbor.fitness == self.solution.fitness:
                    # Pranon edhe lëvizje neutrale (plateau exploration)
                    self.solution = neighbor
                else:
                    improved = False
            
            end_fitness = self.solution.fitness
            self.stats['best_per_restart'].append(end_fitness)
            print(f"Fundi: {end_fitness} (pas {iteration} iteracioneve)")
            
            # Update global best
            if end_fitness > global_best_fitness:
                global_best = deepcopy(self.solution)
                global_best_fitness = end_fitness
                print(f"*** GLOBAL BEST I RI: {global_best_fitness} ***")
        
        # Statistikat finale
        self._print_stats(global_best_fitness)
        
        return global_best
    
    def _find_improving_neighbor(self) -> Optional[Solution]:
        """
        Hill Climbing: Gjej ÇFARËDO fqinj që përmirëson (first improvement).
        Ndryshon nga Steepest Descent që kërkon MË TË MIRËN.
        """
        current_fitness = self.solution.fitness
        scheduled = list(self.solution.selected.scheduled_programs)
        
        # 1. Provo REPLACE
        neighbor = replace(self.solution, self.instance)
        if neighbor.fitness >= current_fitness:
            return neighbor
        
        # 2. Provo SHIFT
        if scheduled:
            program = random.choice(scheduled)
            direction = random.choice(list(TargetBorder))
            mode = random.choice(list(Mode))
            shamt = random.randint(1, config.MAX_SHIFT)
            neighbor = shift_borders(self.instance, self.solution, program, mode, direction, shamt)
            if neighbor is not None and neighbor.fitness >= current_fitness:
                return neighbor
        
        # 3. Provo SWAP
        if len(scheduled) >= 2:
            i = random.randint(0, len(scheduled) - 2)
            neighbor = swap(self.instance, self.solution, scheduled[i], scheduled[i + 1])
            if neighbor.fitness >= current_fitness:
                return neighbor
        
        return None
    
    def _perturb_solution(self, original: Solution) -> Solution:
        """Bëj perturbim për random restart me më shumë randomness."""
        perturbed = deepcopy(original)
        
        # Bëj disa operacione random - numri varet nga random
        num_ops = random.randint(5, 15)  # Rritur nga (3, 8) për më shumë perturbim
        
        for _ in range(num_ops):
            op = random.choice(['replace', 'shift', 'swap'])
            
            if op == 'replace':
                perturbed = replace(perturbed, self.instance)
            elif op == 'shift':
                if perturbed.selected.scheduled_programs:
                    program = random.choice(perturbed.selected.scheduled_programs)
                    direction = random.choice(list(TargetBorder))
                    mode = random.choice(list(Mode))
                    shamt = random.randint(5, 30)  # Rritur nga (5, 20) për shift më të madh
                    shift_result = shift_borders(self.instance, perturbed, program, mode, direction, shamt)
                    if shift_result is not None:
                        perturbed = shift_result
            elif op == 'swap':
                scheduled = perturbed.selected.scheduled_programs
                if len(scheduled) >= 2:
                    # Zgjedh dy indekse të ndryshme RANDOM (jo domosdoshmërisht ngjitur)
                    i = random.randint(0, len(scheduled) - 1)
                    j = random.randint(0, len(scheduled) - 1)
                    if i != j:
                        perturbed = swap(self.instance, perturbed, scheduled[i], scheduled[j])
        
        return perturbed
    
    def _print_stats(self, best_fitness: float):
        """Printo statistikat."""
        print("\n" + "="*60)
        print("STATISTIKA FINALE")
        print("="*60)
        print(f"Best Fitness: {best_fitness}")
        print(f"Total Iterations: {self.stats['total_iterations']}")
        print(f"Improvements: {self.stats['improvements']}")
        print(f"Insertions: {self.stats['insertions']}")
        print(f"Best per Restart: {self.stats['best_per_restart']}")
