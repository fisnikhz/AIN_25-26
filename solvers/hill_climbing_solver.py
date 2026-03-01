from base_solver import BaseSolver
from models.solution.solution import Solution


from io_utils.file_selector import select_file
from io_utils.initial_solution_parser import SolutionParser
from io_utils.instance_parser import InstanceParser


# MOS HARRO MI NDRRU QITO
INSTANCE_PATH = 'filan/fisteku'
INITITAL_SOLUTION_PATH = 'filan/fisteku'

class HillClimbingSolver(BaseSolver):
    def __init__(self, programs):
        super().__init__(programs)

    def solve(self) -> Solution:
        instance = InstanceParser(select_file(INSTANCE_PATH)).parse()
        print(f"Instanca e problemit është ngarukar: {instance}")

        c = SolutionParser(select_file(INITITAL_SOLUTION_PATH)).parse()
        print(f"Zgjidhja kanonike C është ngarukar: {c}")

        f_c: int = c.fitness()

        while True:

            # mos harro qito metoda mi ndrru
            c_mutated = self._mutate(c)
            f_c_mutated = self._fitness(c_mutated)

            if (f_c_mutated < f_c):
                break

            c = c_mutated
            f_c = f_c_mutated

        return c
    

    def _mutate(c):
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

    def _fitness(c):
        '''
            ska me u implementu, veq mos harru me ndreq qysh e thirr fitnesin.
        '''
        pass