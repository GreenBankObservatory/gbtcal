#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse

from projfinder.projFinder import ProjectFinder
from getScanFromProject import getScanFromProject, copyFiles


"""docstring"""

RECEIVERS = [
    "Rcvr1_2",
    "Rcvr2_3",
    "Rcvr4_6",
    "Rcvr8_10",
    "Rcvr12_18",
    "RcvrArray18_26",
    "Rcvr26_40",
    "Rcvr40_52",
    "Rcvr68_92",
    "RcvrArray75_115"
]

REQUIRED_MANAGERS = [
    "Antenna",
    "IF",
    "GO",
    "DCR"
]


def main(destination='.'):
    pf = ProjectFinder()
    for receiver in RECEIVERS:
        managersToSearchFor = [receiver] + REQUIRED_MANAGERS
        results = pf.search(managersToSearchFor)
        if results:
            projectPath, scanNum, scanName = results[0]
            copyFiles(projectPath, scanNum, receiver, scanName,
                      destination=destination)
        else:
            print("No project found for {}".format(managersToSearchFor))
            # projectPath = None
            # scanNum = None
            # scanName = None




# def parse_args():
#     parser = argparse.ArgumentParser()
#     # Add arguments here
#     parser.add_argument()
#     return parser.parse_args()


if __name__ == '__main__':
    # args = parse_args()
    main()
