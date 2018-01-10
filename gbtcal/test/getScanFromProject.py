#!/usr/bin/env python

import argparse
import os
import shutil

from astropy.io import fits

def getScanFromProject(projPath, scan, receiver):
    scanLogHduList = fits.open(os.path.join(projPath, "ScanLog.fits"))
    data = scanLogHduList[1].data

    dataForScan = data[data['SCAN'] == scan]

    return os.path.basename(dataForScan[0]['FILEPATH'])

def copyFiles(projPath, scan, receiver, scanName, destination="."):
    project = os.path.basename(projPath)
    newProjPath = os.path.join(destination, project)
    scanLogPath = os.path.join(projPath, "ScanLog.fits")

    # Copy the entire receiver directory; we don't know exactly
    # what format its contents will be in but we will probably
    # need all of them
    rcvrDir = os.path.join(projPath, receiver)
    # rcvrFitsName = os.listdir(os.path.join(projPath, receiver))[0]
    # rcvrFitsPath = os.path.join(projPath, receiver, rcvrFitsName)
    newRcvrDir = os.path.join(newProjPath, receiver)
    # try:
    #     os.makedirs(newRcvrDir)
    # except OSError:
    #     pass

    if not os.path.isdir(newRcvrDir):
        print("Copying {} to {}".format(rcvrDir, newRcvrDir))
        shutil.copytree(rcvrDir, newRcvrDir)

    print("Copying {} to {}".format(scanLogPath, newProjPath))
    shutil.copy(scanLogPath, newProjPath)
    for manager in ["Antenna", "IF", "GO", "DCR", receiver]:
        oldPath = os.path.join(projPath, manager, scanName)
        newPath = os.path.join(destination, project, manager, scanName)

        try:
            os.makedirs(os.path.join(destination, project, manager))
        except OSError:
            pass
        with open(os.path.join(destination, project, "README"), 'w+') as f:
            f.write("Data for scan {}\n".format(scan))

        print("Copying {} to {}".format(oldPath, newPath))
        shutil.copy(oldPath, newPath)



def parseArgs():
    """Parse CLI arguments and return them"""

    parser = argparse.ArgumentParser()
    parser.add_argument("projPath",
                        help="The path to the project directory")
    parser.add_argument("scan",
                        help="The scan number you wish to process",
                        type=int)
    parser.add_argument("receiver",
                        help="The name of the receiver")
    parser.add_argument("-o", "--output",
                        help="The path to copy files to",
                        default=".")

    return parser.parse_args()


if __name__ == '__main__':
    args = parseArgs()
    scanName = getScanFromProject(args.projPath, args.scan, args.receiver)
    copyFiles(args.projPath, args.scan, args.receiver, scanName, args.output)
