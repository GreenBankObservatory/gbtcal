#!/usr/bin/env python

import os
import numpy
import traceback
from datetime import datetime
from astropy.io import fits

from gbtcal.calibrate import calibrate

SCRIPTPATH = os.path.dirname(os.path.abspath(__file__))

def hasRedundantScanNums(projPath):
    "Projects that repeat scan numbers are problematic"

    # Try to open the scan log fits file
    scanLog = fits.getdata(os.path.join(projPath, "ScanLog.fits"))

    scanNums = scanLog['SCAN']

    prevScan = scanNums[0]
    for scanNum in scanNums:
        if scanNum - prevScan < 0:
            print("WARNING: Possibly redundant scan! Scan {} comes "
                  "after {} in {}".format(projPath, scanNum, prevScan))
            return True
        prevScan = scanNum

    return False


def testAllResults():
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

    projLimit = 10
    scanLimit = 10

    # we simply aren't supporting all receivers
    # Rcvr18_26: The K-band receiver has been retired and is
    # too different from the others to be worth the effort
    skipReceivers = ['Rcvr18_26']

    numReceivers = len(dataSrcDct.keys())
    nRcvr = 0

    for receiver, projInfos in dataSrcDct.items():
        nRcvr += 1
        print("receiver {}, {} of {}".format(receiver, nRcvr, numReceivers))
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
            print("project {} of {}".format(pi, len(projInfos)))
            print(projInfo)

            try:
                projName, projParentPath, testScans = projInfo
            except ValueError as e:
                # print(traceback.format_exc(e))
                print("Invalid projInfo: {}".format(projInfo))
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
                    print("Could not find sparrow results file {}"
                          .format(sparrow_results_file))
                    dataProblems[MISSING].append(sparrow_results_file)
                    break
                except:
                    print("Unknown error in evaluating sparrow file")
                    dataProblems[MALFORMED].append(sparrow_results_file)
                    break

                print("projPath: {}\n"
                      "receiver: {}\n"
                      "scanNum: {}"
                      .format(projPath, receiver, scanNum))

                # any results to check against?
                if resultsDict == {}:
                    print("Empy sparrow results dict!")
                    dataProblems[EMPTY].append(sparrow_results_file)
                    break

                # if this project has redundant scan numbers, we can't
                # trust the results
                if hasRedundantScanNums(projPath):
                    print("WARNING: skipping this scan: ", projPath, scanNum)
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
    for spKey, expected in resultsDict.items():
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
            print("Something went wrong", traceback.format_exc())
            return False, "Exception"
        if not numpy.allclose(actual, expected):
            al = arraySummary(actual),
            el = arraySummary(expected),
            print("Test for {} failed: {} != {}".format(spKey, al, el))
            return False, "Mismatched"

    print(projPath, scanNum, "Results MATCH!")
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
    numProblems = sum([len(v) for k, v in dataProblems.items()])

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
        for k, vs in dataProblems.items():
            f.write("* Type: {}\n".format(k))
            for v in vs:
                f.write("{}\n".format(v))


if __name__ == '__main__':
    testAllResults()
