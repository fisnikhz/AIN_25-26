from base_solver import BaseSolver
from models.solution.solution import Solution
from models.solution.schedule import Schedule
from models.instance.instance_data import InstanceData

from evaluators.base_evaluator import BaseEvaluator

from io_utils.file_selector import select_file
from io_utils.initial_solution_parser import SolutionParser
from io_utils.instance_parser import InstanceParser


# MOS HARRO MI NDRRU QITO
INSTANCE_PATH = 'filan/fisteku'
INITITAL_SOLUTION_PATH = 'filan/fisteku'

class HillClimbingSolver(BaseSolver):

    def __init__(self, instance_path: str, init_solution_path: str):
        instance = InstanceParser(select_file(instance_path)).parse()

        evaluator = BaseEvaluator(instance)
        init_schedule = SolutionParser(select_file(init_solution_path)).parse()
        unselected_ids = self.__get_unselected_ids(instance, init_schedule)

        solution = Solution(evaluator=evaluator, selected=init_schedule, unselected_ids=unselected_ids)

        super().__init__(solution)

    def solve(self) -> Solution:

        while True:
            fitness = self.solution.fitness

            solution_mutated = self.__mutate()
            fitness_mutated = solution_mutated.fitness

            if (fitness_mutated < fitness):
                break

            self.solution = solution_mutated
            fitness = fitness_mutated

        return self.solution
    
    def __mutate() -> Solution:
        '''
            perdore ni strategji qfare t'dush per me thirr njanin prej 
            operatorve: swap() ose shift()
        '''
        '''
            coin = flip()
            if coin:
                swap(random_args)
            else:
                shift(random_args)
        '''
        pass

    def __get_unselected_ids(instance: InstanceData, schedule: Schedule) -> list[str]:
        
        pass