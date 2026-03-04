from solvers.base_solver import BaseSolver
from evaluators.base_evaluator import BaseEvaluator
from io_utils.file_selector import select_file
from io_utils.initial_solution_parser import SolutionParser
from io_utils.instance_parser import InstanceParser
from models.solution.solution import Solution
from operators.swap import swap


# MOS HARRO MI NDRRU QITO
INSTANCE_PATH = 'filan/fisteku'
INITITAL_SOLUTION_PATH = 'filan/fisteku'

class HillClimbingSolver(BaseSolver):

    def __init__(self, solution: Solution):
        super().__init__(solution)
        
        self.unselected_ids = self.__get_unselected_ids(self.solution.evaluator.instance)

    def solve(self) -> Solution:
        print(f"Initial fitness: {self.solution.fitness}")
        
        iteration = 0
        while True:
            iteration += 1
            neighbor = self.__mutate() # This calls your swap
            
            if neighbor.fitness > self.solution.fitness:
                print(f"Iteration {iteration}: Found better fitness! {neighbor.fitness}")
                self.solution = neighbor
            else:
                if iteration % 100 == 0:
                    print(f"Still searching... (Iteration {iteration})")
                
                if iteration > 5000: # Temporary safety cap for testing
                    print("Reached iteration limit or local optimum.")
                    break
                    
        return self.solution
    
    def __mutate(self) -> Solution:
        import copy
        mutated_solution = copy.deepcopy(self.solution)
        
        return swap(mutated_solution, self.solution.evaluator.instance)

    def __get_unselected_ids(self, instance) -> list[str]:
        selected_ids = {p.program_id for p in self.solution.selected}
        
        unselected = []
        for channel in instance.channels:
            for program in channel.programs:
                if program.program_id not in selected_ids:
                    unselected.append(program.program_id)
        
        return unselected