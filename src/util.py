from __future__ import print_function
import sys

def wprint(string):
    """Given a string, prepend ERROR to it and print it to stderr"""

    print("WARNING: {}".format(string), file=sys.stderr)

def eprint(string):
    """Given a string, prepend ERROR to it and print it to stderr"""

    print("ERROR: {}".format(string), file=sys.stderr)
