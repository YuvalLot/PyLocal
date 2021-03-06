
from Match import MatchDictionary
from util import processParen, smart_replace
import random


class Predicate:
    """

    class Predicate holds information about predicates, building blocks of LCL.
    Predicates are so called "functions" that describe a quality or relation that one, two or more objects hold.
    for example, a Color predicate might relate objects with colors.

    this class is important during interpretation of rules - built dynamically, i.e. line by line.
    during interpretation an empty predicate class is created by __init__, and then, by use of "case ... then ...", is accepting new cases.

    during query search the predicate is responsible for pattern matching (using MatchDictionary).
    the match method goes through cases and tries to match.

    """

    created = 0

    def __eq__(self, other):
        """

        find if two predicates are completely equal (using their id)

        :param other: another Predicate
        :return: Boolean
        """
        return self.id == other.id

    def __init__(self, interpreter, name, rec, rand):
        """
        Initiate an empty Predicate.
        Predicates are the building blocks of LCL. They provide the information needed to solve Queries.

        :param interpreter: A Interpreter Object
        :param name: A String denoting the name
        :param rec: A Boolean denoting whether a predicate is recursive (stops looking after found matches)
        :param rand: A Boolean denoting whether a predicate is random
        """
        self.name = name  # Predicate Name
        self.cases = []  # Predicate cases to match
        self.then = []  # Predicate searches to do if matched with case
        self.basic = []  # Predicate Facts
        self.nope = []  # Predicate False
        self.recursive = rec  # If the predicate is recursive, as son as it matches it stops looking. (Opposite of generative)
        self.random = rand  # Whether to check solutions
        self.count = 0  # Count of cases
        self.interpreter = interpreter  # Interpreter for predicate
        self.id = Predicate.created
        Predicate.created += 1

    # Adds a case
    def addCase(self, to_match, then, insert=False):
        """
        Add a translation case to predicate.

        :param to_match: str, the pattern needs matching
        :param then: str, what to search if the match was successful
        :param insert: Boolean - add it at the end
        :return: None
        """
        to_match = to_match.strip()
        if len(to_match) == 0:

            if insert:
                self.cases = [to_match] + self.cases
                self.then = [then] + self.then
                self.count += 1
                return

            self.cases.append('')
            self.then.append(then)
            self.count += 1
            return

        to_match = processParen(to_match)
        if not to_match:
            self.interpreter.raiseError(f"Error: Incomplete parentheses in predicate {self.name}")
            return

        then = processParen(then)
        if not then:
            self.interpreter.raiseError(f"Error: Incomplete parentheses in predicate {self.name}")
            return

        if len(to_match) == 0:
            if insert:
                self.cases = [to_match] + self.cases
                self.then = [then] + self.then
                self.count += 1
                return

            self.cases.append('')
            self.then.append(then)
            self.count += 1
            return

        if insert:
            self.cases = [to_match] + self.cases
            self.then = [then] + self.then
            self.count += 1
            return

        self.cases.append(to_match)
        self.then.append(then)
        self.count += 1

    # adds a fact
    def addBasic(self, to_match, insert=False):
        """
        Adding a Fact to predicate.

        :param to_match: str, pattern to match
        :param insert: boolean, denoting whether to add in the beginning
        :return: None
        """

        to_match = to_match.strip()
        if len(to_match) == 0:

            if insert:
                self.basic = [''] + self.basic
                return

            self.basic.append('')
            return
        to_match = processParen(to_match)
        if not to_match:
            self.interpreter.raiseError(f"Error: Incomplete parentheses in predicate {self.name}")
        if len(to_match) == 0:
            if insert:
                self.basic = [''] + self.basic
                return

            self.basic.append('')
            return

        if insert:
            self.basic = [to_match] + self.basic
            return

        self.basic.append(to_match)

    # adds a false fact
    def addNot(self, to_match, insert=False):
        """
        Add a terminal case - stops looking if matched. not that useful but sometimes important.

        :param to_match: str, pattrn to match
        :param insert: boolean, add in the beginning
        :return:
        """
        to_match = to_match.strip()
        if len(to_match) == 0:

            if insert:
                self.nope = [''] + self.nope
                return

            self.nope.append('')
            return
        to_match = processParen(to_match)
        if not to_match:
            self.interpreter.raiseError(f"Error: Incomplete parentheses in predicate {self.name}")
        if len(to_match) == 0:
            if insert:
                self.nope = [''] + self.nope
                return
            self.nope.append('')
            return

        if insert:
            self.nope = [to_match] + self.nope
            return

        self.nope.append(to_match)

    # finds a match.
    def match(self, pattern):
        """
        Given a pattern, look through all cases and determine if there exists a match.
        if match is basic, return basic solution.
         if match is terminal, return False.
        if match is translational, return the new search that has to be done, and a way (the backward dictionary) to translate from solutions of the new
        search back to the parameters given in the pattern. This is the fundamental idea of back chaining, used to solved queries.

        :param pattern: str
        :return: Generator of (search, forward, backward), False
        """

        pattern = processParen(pattern)
        if pattern is False or pattern is None:
            self.interpreter.raiseError("Error: Incomplete Parentheses")
            return

        # Looking for false facts
        for nope in self.nope:
            t = MatchDictionary.match(self.interpreter, pattern, nope)
            if t and not t[2]:  # only in the case the patterns matched AND no wiggle room
                return

        if self.random:
            # print("RANDOM")
            while True:
                if len(self.basic) == 0 and self.count == 0:
                    return
                ch = []
                if len(self.basic) != 0:
                    ch.append('basic')
                if self.count != 0:
                    ch.append('translation')
                indices_name = random.choice(ch)
                if indices_name == 'basic':
                    basic = random.choice(self.basic)
                    t = MatchDictionary.match(self.interpreter, pattern, basic)
                    if t:
                        # print(f"Match basic: {t[0]},{t[1]}")
                        yield 1, t[1], t[0]
                        if self.recursive:
                            return
                if indices_name == 'translation':
                    i = random.randint(0, self.count - 1)
                    t = MatchDictionary.match(self.interpreter, pattern, self.cases[i])
                    if t:
                        # print(f"Matched with {self.cases[i]}: {t[0]},{t[1]}")
                        then = self.then[i]
                        then = smart_replace(then, t[0])
                        yield then, t[1], t[0]
                        if self.recursive:
                            return

        for basic in self.basic:
            t = MatchDictionary.match(self.interpreter, pattern, basic)
            if t:
                yield 1, t[1], t[0]
                if self.recursive:
                    return

        for i in range(self.count):
            t = MatchDictionary.match(self.interpreter, pattern, self.cases[i])
            if t:
                then = self.then[i]
                then = smart_replace(then, t[0])
                yield then, t[1], t[0]
                if self.recursive:
                    return

    # To str
    def __str__(self):
        """
        Called by Listing. Returns (as str) all important information about predicate)

        :return: str representation of predicate class
        """
        s = f"Predicate {self.name}"
        if self.recursive:
            s += ", Recursive"
        if self.random:
            s += ", Random"

        s += ":\n"

        for basic in self.basic:
            s += f"   Basic Match: {basic}\n"
        for no in self.nope:
            s += f"   Terminal Match: {no}\n"
        for i in range(self.count):
            s += f"   If Matched with {self.cases[i]}, then Search {self.then[i]}\n"

        return s
