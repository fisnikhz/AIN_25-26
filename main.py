from io_utils.parser import parse_input
from io_utils.writer import write_solution
from solvers.greedy_solver import GreedySolver

def main():
    input_file = "input.json"
    programs = parse_input(input_file)
    
    solver = GreedySolver(programs)
    
    solution = solver.solve()
    print(f"Final Solution: {solution}")
    
    output_file = "output.json"
    write_solution(solution, output_file)
    print(f"Results saved to {output_file}")

if __name__ == "__main__":
    main()
