#!/usr/bin/env python

import os
import sys
import numpy
import traceback
import argparse
from datetime import datetime
from astropy.io import fits

from gbtcal.calibrate import calibrate

SCRIPTPATH = os.path.dirname(os.path.abspath(__file__))

# This is a simple module for comparing results computed by gbtcal
# with that originally computed by Sparrow (GFM).
# The Sparrow results live in files with descriptive filenames,
# such as <projectname>.<scannumber>.<receiver>.
# The home of the data that these Sparrow results were created from
# live in a separate file, organized by receiver, project path, and
# scan numbers.
# The basic flow of these tests is to:
#    * Find where all the DCR data lives in the archive by reading the
#      above mentioned file
#    * For each of these scans:
#       * Computing the various DCR Calibration results
#       * Compare these results to what are in the Sparrow files
#    * All results are printed to a report, including any problems
#      encountered, besides the obvious mismatching results

def hasRedundantScanNums(projPath):
    "Projects that repeat scan numbers are problematic"

    # Try to open the scan log fits file
    scanLog = fits.getdata(os.path.join(projPath, "ScanLog.fits"))

    scanNums = scanLog['SCAN']

    prevScan = scanNums[0]
    for scanNum in scanNums:
        if scanNum - prevScan < 0:
            print(("WARNING: Possibly redundant scan! Scan {} comes "
                  "after {} in {}".format(projPath, scanNum, prevScan)))
            return True
        prevScan = scanNum

    return False


def testAllResults(projLimit=None, scanLimit=None):
    "Compare ALL the sparrow results to what this code repo produces"

    beginTime = datetime.now()

    # maintain some metrics for the final report
    numChecked = 0
    numCompared = 0
    REDUNDANT = "Redundant Scans"
    MISSING = "Missing Sparrow Results File"
    MALFORMED = "MALFORMED Sparrow Results File"
    EMPTY = "Empty Sparrow Results File"
    INVALIDPROJ = "Invalid Project Info"
    EXCEPTION = "Exception during calibration"
    dataProblems = {
        REDUNDANT: [],
        INVALIDPROJ: [],
        MISSING: [],
        MALFORMED: [],
        EMPTY: [],
        EXCEPTION: []
    }
    nonMatchingResults = []

    # where are all the sparrow result files?
    sparrow_results_dir = '/home/scratch/pmargani/allCalDcrData'

    # where is the location of all the DCR data we want to test?
    dataSrcDctFn = "{}/rcvrDCRscans.txt".format(SCRIPTPATH)
    with open(dataSrcDctFn, 'r') as f:
        dataSrcDct = eval(f.read())

    # we simply aren't supporting all receivers
    # Rcvr18_26: The K-band receiver has been retired and is
    # too different from the others to be worth the effort
    skipReceivers = ['Rcvr18_26']

    numReceivers = len(list(dataSrcDct.keys()))
    nRcvr = 0

    for receiver, projInfos in list(dataSrcDct.items()):
        nRcvr += 1
        print(("receiver {}, {} of {}".format(receiver, nRcvr, numReceivers)))
        if receiver in skipReceivers:
            continue

        # Looks like there was a bug in the data collection and this
        # list is not completely flat. Easy enough, we'll just flatten
        # it
        projInfosFlat = []
        for item in projInfos:
            if type(item) == list:
                projInfosFlat.extend(item)
            else:
                projInfosFlat.append(item)

        # Limit the projs to test?
        projInfos = projInfosFlat if projLimit is None \
            else projInfosFlat[:projLimit]

        for pi, projInfo in enumerate(projInfos):
            print(("project {} of {}".format(pi, len(projInfos))))
            print(projInfo)

            try:
                projName, projParentPath, testScans = projInfo
            except ValueError as e:
                # print(traceback.format_exc(e))
                print(("Invalid projInfo: {}".format(projInfo)))
                dataProblems[INVALIDPROJ].append(projInfo)
                continue

            projPath = os.path.join(projParentPath, projName)

            # limit the scans to test?
            scans = testScans if scanLimit is None else testScans[:scanLimit]

            for scanNum in scans:
                numChecked += 1
                sparrow_result_name = (
                    "{proj}:{scan}:{rcvr}".format(proj=projName,
                                                  scan=scanNum,
                                                  rcvr=receiver)
                )
                sparrow_results_file = os.path.join(sparrow_results_dir,
                                                    sparrow_result_name)

                try:
                    with open(sparrow_results_file) as f:
                        resultsDict = eval(f.read())
                except IOError as e:
                    print(e)
                    print(("Could not find sparrow results file {}"
                          .format(sparrow_results_file)))
                    dataProblems[MISSING].append(sparrow_results_file)
                    break
                except:
                    print("Unknown error in evaluating sparrow file")
                    dataProblems[MALFORMED].append(sparrow_results_file)
                    break

                print(("projPath: {}\n"
                      "receiver: {}\n"
                      "scanNum: {}"
                      .format(projPath, receiver, scanNum)))

                # any results to check against?
                if resultsDict == {}:
                    print("Empy sparrow results dict!")
                    dataProblems[EMPTY].append(sparrow_results_file)
                    break

                # if this project has redundant scan numbers, we can't
                # trust the results
                if hasRedundantScanNums(projPath):
                    print(("WARNING: skipping this scan: ", projPath, scanNum))
                    dataProblems[REDUNDANT].append(projPath)
                    break

                # FINALLY, we can actually compare our new results against
                # those from the sprarrow results file
                match, msg = compare(projPath, scanNum, resultsDict, receiver)

                if match:
                    numCompared += 1

                if not match:
                    # why did the compare fnc fail?
                    info = (projPath, scanNum, receiver)
                    if msg == "Mismatched":
                        # our code produced different results, so
                        # a comparison was made
                        numCompared += 1
                        nonMatchingResults.append(info)
                    else:
                        # our code couldn't produce restuls,
                        # so no comparison happened
                        dataProblems[EXCEPTION].append(info)

    reportResults(numChecked,
                  numCompared,
                  dataProblems,
                  nonMatchingResults,
                  beginTime)


def arraySummary(array):
    return "[{} ... {}]".format(array[0], array[-1])


def compare(projPath, scanNum, resultsDict, receiver):
    "compare sparrow reults for this scan with ours"

    # we are already testing for this upstream
    # if hasRedundantScanNums(projPath):
    #     print("WARNING: skipping this scan: ", projPath, scanNum)
    #     return False, "Redundant Scans"

    # only check against the keys that exist in both:
    for spKey, expected in list(resultsDict.items()):
        spCalMode, spPolMode = spKey

        # sparrow does some funky things for some receivers, that we
        # don't want to do.  For instance, you can ask for the Raw,
        # YR values for Argus, though it has only XL data.  Sparrow
        # will quietly give you the XL data instead.  We don't want
        # to do that; instead we complain if you ask for that
        if receiver == 'RcvrArray75_115' and spPolMode in ['Avg', 'YR']:
            break
        # Sparrow produces bad results for Ka DualBeam
        if receiver == 'Rcvr26_40' and spCalMode == 'DualBeam':
            break

        try:
            actual = calibrate(projPath, scanNum, spCalMode, spPolMode)
        except:
            print(("Something went wrong", traceback.format_exc()))
            return False, "Exception"

        # The sparrow results for (Raw, Avg) are still ints,
        # so we need to take that into account
        if spKey == ('Raw', 'Avg'):
            actual = actual.astype(int)

        if not numpy.allclose(actual, expected):
            al = arraySummary(actual),
            el = arraySummary(expected),
            print(("Test for {} failed: {} != {}".format(spKey, al, el)))
            return False, "Mismatched"

    print((projPath, scanNum, "Results MATCH!"))
    return True, None


def reportResults(numChecked,
                  numCompared,
                  dataProblems,
                  nonMatchingResults,
                  beginTime):

    now = datetime.now()
    nowStr = now.strftime("%Y_%m_%d_%H_%M")
    fn = "DcrDecodeRegressionReport.{}.txt".format(nowStr)

    # TBF: why the hell doesn't this work???
    # print(beginTime, now, (beginTime - now).seconds)
    # elapsedMins = (beginTime - now).seconds / 60.

    numMismatched = len(nonMatchingResults)
    numPassed = numCompared - numMismatched
    numProblems = sum([len(v) for k, v in list(dataProblems.items())])

    prcPassed = 100. * (numPassed / float(numCompared))
    prcCompared = 100. * (numCompared / float(numChecked))

    with open(fn, 'w') as f:
        f.write("*** DCR Decode Regression test for {}\n\n".format(now))
        # f.write("Elapsed Minutes: {}\n".format(elapsedMins))
        f.write("Percentage compared that passed {}%\n".format(prcPassed))
        f.write("Percentage compared of all checked {}%\n".format(prcCompared))
        f.write("Num Scans Checked: {}\n".format(numChecked))
        f.write("Num Scans Compared: {}\n".format(numCompared))
        f.write("Num Scans Mismatched: {}\n".format(numMismatched))
        f.write("Num Scans With Problems: {}\n".format(numProblems))
        f.write("*** Details:\n")
        f.write("*** Mismatched Results:\n")
        for n in nonMatchingResults:
            print(n)
            f.write("{}\n".format(n))
        f.write("*** Data Problems:\n")
        for k, vs in list(dataProblems.items()):
            f.write("* Type: {}\n".format(k))
            for v in vs:
                f.write("{}\n".format(v))


def parseArgs():
    
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--projLimit",
                        help="Test just first 'projLimit' projects for all receivers")
    parser.add_argument("--scanLimit",
                        help="Test just first 'scanLimit' scans for all projects")
    return parser.parse_args()


if __name__ == '__main__':
    args = parseArgs()
    if args.projLimit is None and args.scanLimit is None:
        print("You have choosen to run the full regression test suite.")
        print("This may take days.  Are you sure? (y/n)")
        sure = input()
        if sure == "y":
            print("OK, performing full regression test suite.")
        else:
            print("You didn't type 'y', so we're bailing")
            sys.exit(0)
    testAllResults(int(args.projLimit), int(args.scanLimit))
