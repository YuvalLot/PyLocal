
from copy import deepcopy
from Match import MatchDictionary
from util import processParen, splitWithoutParen, outString, smart_replace, match_type, var_in_query

fixed_search = []


class Domain:
    """
    Domain Predicate -
    uses constraint propagation and look-ahead searching to solve
    problems with constraints.
    """

    def __init__(self, intrp, name):
        """
        A domain.

        :param intrp: Interpreter
        :param name: String
        """
        self.interpreter = intrp
        self.name = name
        self.variables = []
        self.raw_vars = ""
        self.range_searches = {}
        self.constraints = {}
        self.eliminations = {}
        self.ranges = {}
        self.final = ""
        self.when = {}
        self.deleted = False

    def complete(self):
        """
        Checks if the domain has a range for every single variable.

        :return: bool
        """
        if set(self.variables) != set(self.range_searches.keys()):
            return False
        return True

    def insert_variables(self, variables:str, line):
        """
        Inserts variables to the domain predicate.

        :param variables: str
        :param line: int
        :return: bool
        """
        a, _, b = variables.partition("(")
        b = b[:-1]
        if a.isnumeric() and match_type(b) == "var":
            self.variables = [f"{b}{i}" for i in range(1, int(a)+1)]
            print(self.variables)
            return True
        self.raw_vars = variables
        self.variables = splitWithoutParen(variables)
        if any(match_type(var) != "var" for var in self.variables):
            self.interpreter.raiseError(f"Error: Illegal variables of domain {self.name}, in line {line}")
            return False
        return True

    def shut_down(self):
        """
        Shuts down this domain

        :return:
        """
        self.deleted = True

    def insert_range(self, variable, range_search, line):
        """
        Inserts a variable range to the domain predicate.

        :param variable: str
        :param range_search: str
        :param line: int
        :return: bool
        """
        if variable == "?all":
            for variable in self.variables:
                if variable in self.range_searches:
                    continue
                self.range_searches[variable] = smart_replace(range_search, {"?all": variable})
            return True
        if variable not in self.variables:
            self.interpreter.raiseError(f"Error: Variable {variable} not part of Domain {self.name}, in line {line}")
            return False
        range_search = processParen(range_search)
        if not range_search:
            self.interpreter.raiseError(f"Error: Illegal range search in Domain {self.name} of variable {variable}, in line {line}")
            return False
        if variable in self.range_searches:
            self.interpreter.raiseError(f"Error: In Domain {self.name}, variable {variable} already has a defined range, in line {line}")
            return False
        self.range_searches[variable] = range_search
        return True

    def insert_constraint(self, const, when, line):
        """
        Inserts a constraint.

        :param const: str
        :param when: str
        :param line: int
        :return: bool
        """
        const = processParen(const)
        if not const:
            self.interpreter.raiseError(f"Error: In Domain {self.name}, constraint {const} illegal, in line {line}")
            return False
        self.constraints[const] = {var for var in self.variables if var_in_query(const, var)}
        self.when[const] = when
        return True

    def insert_elimination(self, elim, when, line):
        """
        Inserts a constraint.

        :param elim: str
        :param when: str
        :param line: int
        :return: bool
        """
        elim = processParen(elim)
        if not elim:
            self.interpreter.raiseError(f"Error: In Domain {self.name}, elimination {elim} illegal, in line {line}")
            return False
        self.eliminations[elim] = {var for var in self.variables if var_in_query(elim, var)}
        self.when[elim] = when
        return True

    def insert_final(self, final):
        """
        Inserts a final assertion

        :param final: str
        """
        self.final = final

    def generate_ranges(self, depth):
        """
        Generates variable ranges.

        :param depth: Counter
        """
        if self.ranges:
            return
        for var in self.variables:
            if var not in self.range_searches:
                self.ranges = None
                return
            self.ranges[var] = set()
            for search in self.interpreter.mixed_query(self.range_searches[var], 0, depth, True):
                if var in search:
                    self.ranges[var].add(search[var])

    def search(self, depth, query_pat):
        """
        Public method to generate solutions. This is the main method of the class, that does the search.

        :param depth: Counter
        :param query_pat: str
        :return: generator[dict]
        """
        parts = splitWithoutParen(query_pat)
        if len(parts) != len(self.variables):
            # print(parts, self.variables)
            return
        self.generate_ranges(depth)

        ranges = deepcopy(self.ranges)
        fixed = {}

        # print(f"Original ranges {ranges}")
        for i, part in enumerate(parts):
            var = self.variables[i]
            for option in self.ranges[var]:
                if not MatchDictionary.match(self.interpreter, part, option):
                    ranges[var].remove(option)
                if len(ranges[var]) == 0:
                    return
                if len(ranges[var]) == 1:
                    fixed[var] = next(iter(ranges[var]))
                    del ranges[var]
                    break

        consts = deepcopy(self.constraints)
        elims = deepcopy(self.eliminations)
        already = set()

        self.update_range(depth, ranges, fixed, consts, elims, already)

        print(f"domain ranges {ranges}, with fixed {fixed}\n")
        yield from self.solve(depth, ranges, fixed, consts, elims, already)

    def solve(self, depth, ranges, fixed, rel_const, rel_elim, already):
        """
        Solves a constraint problem.
        ranges represents the ranges of variables in the constraint problem.
        fixed represents the fixed variables, that had been instantiated.
        rel_const represents the relevant constraints that have yet to be solved.
        rel_elim represents the relevant eliminations that have yet to be solved.

        :param depth: Counter
        :param ranges: dict[str, set[str]]
        :param fixed: dict[str, str]
        :param rel_const: dict[str, set[str]]
        :param rel_elim: dict[str, set[str]]
        :param already: set[str]
        :return: generator[dict]
        """

        if depth.count < 0:
            return

        if self.deleted:
            return

        # if there are any ranges with length 1 or 0
        flag = True
        while flag:
            flag = False
            for var in list(ranges.keys()):
                if len(ranges[var]) == 0:
                    return
                if len(ranges[var]) == 1:
                    flag = True
                    fixed[var] = ranges[var].pop()
                    del ranges[var]
            if flag:
                if not self.update_range(depth, ranges, fixed, consts=rel_const, elims=rel_elim, already=already):
                    return

        if len(ranges) == 0:
            if self.final == "":
                yield fixed
                return True
            for _ in self.interpreter.mixed_query(smart_replace(self.final, fixed), 0, depth, True):
                yield fixed
                return True
            return False

        var = min(ranges.keys(), key=lambda k: len(ranges[k]))
        rng = ranges[var]

        for option in rng:

            if self.deleted:
                return

            new_ranges = deepcopy(ranges)
            del new_ranges[var]
            new_fixed = deepcopy(fixed)
            new_fixed[var] = option
            new_consts = deepcopy(rel_const)
            new_elim = deepcopy(rel_elim)
            new_already = deepcopy(already)

            if not self.update_range(depth, new_ranges, new_fixed, new_consts, new_elim, new_already):
                continue

            yield from self.solve(depth, new_ranges, new_fixed, new_consts, new_elim, new_already)

    def update_range(self, depth, ranges, fixed, consts, elims, already):
        """
        Updated the ranges based on the constraints, eliminations and fixed variables.

        :param depth: Counter
        :param ranges: dict[str, set[str]]
        :param fixed: dict[str, str]
        :param consts: dict[str, set[str]]
        :param elims: dict[str, set[str]]
        :param already: set[str]
        :return: bool
        """

        if self.deleted:
            return

        for const in list(consts.keys()):
            possible_sols = {}  # dictionary between variables and their solutions
            new_set = set()  # to be : a set of all variables that appear in this const, and do not have an evaluation yet

            # Updating the constraint dictionary
            for var in consts[const]:
                if var not in fixed:
                    possible_sols[var] = set()
                    new_set.add(var)

            consts[const] = new_set
            original_const = const
            const = smart_replace(const, fixed)

            if const in already:
                # already searched this constraint
                continue
            else:
                already.add(const)

            # checking for when conditions
            try:
                if self.when[original_const] != "":
                    sol_gen = self.interpreter.mixed_query(smart_replace(self.when[original_const], fixed), 0, depth, True)
                    while next(sol_gen) in ["Print", "Request"]:
                        pass
            except StopIteration:
                # for when
                continue

            if len(possible_sols) == 0:
                try:
                    sol_gen = self.interpreter.mixed_query(const, 0, depth, True)
                    while next(sol_gen) in ["Print", "Request"]:
                        pass
                    del consts[original_const]
                    continue
                except StopIteration:
                    return False

            for sol in self.interpreter.mixed_query(const, 0, depth, True):

                if type(sol) != dict:
                    continue

                for var in possible_sols:
                    if var in sol:
                        possible_sols[var].add(sol[var])

            for var in possible_sols:
                if any(match_type(possible_value) == "var" for possible_value in possible_sols[var]):
                    continue
                ranges[var] = ranges[var].intersection(possible_sols[var])
                if len(ranges[var]) == 0:
                    # print(f"Exited due to {const}")
                    return False

        for elim in list(elims.keys()):
            impossible_sols = {}

            new_set = set()

            for var in elims[elim]:
                if var in fixed:
                    continue
                impossible_sols[var] = set()
                new_set.add(var)

            elims[elim] = new_set

            original_elim = elim
            elim = smart_replace(elim, fixed)

            if elim in already:
                continue
            else:
                already.add(elim)

            try:
                if self.when[original_elim] != "":
                    next(self.interpreter.mixed_query(smart_replace(self.when[original_elim], fixed), 0, depth, True))
            except StopIteration:
                continue

            if len(impossible_sols) == 0:
                continue

            for sol in self.interpreter.mixed_query(elim, 0, depth, True):
                # print(f"Solution to {elim} is {sol}, with possible solutions {possible_sols}")
                for var in impossible_sols:
                    if var in sol:
                        impossible_sols[var].add(sol[var])

            for var in impossible_sols:
                ranges[var] = ranges[var].difference(impossible_sols[var])
                if len(ranges[var]) == 0:
                    return False

        return True
