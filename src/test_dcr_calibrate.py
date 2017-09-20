import ast
import os
from astropy.io import fits

from dcr_calibrate import calibrateAll


def hasRedundantScanNums(projPath):

    # Try to open the scan log fits file
    scanLog = fits.getdata(os.path.join(projPath, "ScanLog.fits"))

    scanNums = scanLog['SCAN']

    prevScan = scanNums[0]
    for scanNum in scanNums:
        if scanNum - prevScan < 0:
            print("WARNING: Possibly redundant scan! Scan {} comes after {} in {}".format(projPath, scanNum, prevScan))
            return True
        prevScan = scanNum

    return False


def testAllResults():

    numChecked = 0
    bads = []

    sparrow_results_dir = '/home/scratch/pmargani/allCalDcrData'

    dataSrcDctFn = "/users/pmargani/tmp/rcvrDCRscans.txt"
    with open(dataSrcDctFn, 'r') as f:
        dataSrcDct = ast.literal_eval(f.read())

    # skipRcvrs = ["Rcvr68_92", "RcvrArray75_115", 'Rcvr26_40', 'Rcvr12_18', 'Rcvr18_26']
    skipRcvrs = [
        "Rcvr68_92", # W band doesn't use Rx cal
        "RcvrArray75_115", # Argus doesn't use Rx cal
        'Rcvr18_26', # K - Sparrow can't seem to do dual beam
        # 'RcvrArray18_26', # KFPA - beams seem to be missing data a lot
        'Rcvr26_40', # Ka - how to calibrate this data???
    ]

    # dataSrcDct = {
    #     'Rcvr18_26': [('AGBT11A_060_08', '/home/archive/science-data/11A', [1])]
    # }

    for receiver, projInfos in dataSrcDct.items():
        print("receiver", receiver)

        if receiver in skipRcvrs:
            print("skipping rcvr", receiver)
            continue
        # if receiver not in ['RcvrArray18_26']:
        #     continue

        # Looks like there was a bug in the data collection and this
        # list is not completely flat. Easy enough, we'll just flatten
        # it
        projInfosFlat = []
        for item in projInfos:
            if type(item) == list:
                projInfosFlat.extend(item)
            else:
                projInfosFlat.append(item)

        for projInfo in projInfosFlat[:2]:
            print(projInfo)
            try:
                projName, projParentPath, scans = projInfo
            except ValueError as e:
                print(traceback.format_exc(e))
                print("Invalid projInfo: {}".format(projInfo))

            projPath = os.path.join(projParentPath, projName)

            # print("Processing every {}th scan out of {} total from project {}"
                  # .format(scanStep, len(scans), projName))
            for scanNum in scans[:1]:
                sparrow_result_name = (
                    "{proj}:{scan}:{rcvr}".format(proj=projName,
                                                  scan=scanNum,
                                                  rcvr=receiver)
                )
                sparrow_results_file = os.path.join(sparrow_results_dir,
                                                    sparrow_result_name)

                try:
                    with open(sparrow_results_file) as f:
                        resultsDict = ast.literal_eval(f.read())
                except IOError as e:
                    print(e)
                    print("Could not find sparrow results file {}"
                          .format(sparrow_results_file))
                    break
                except Exception as e:
                    print("Unknown error in evaluating sparrow file")
                    break

                print("projPath: {}\n"
                      "receiver: {}\n"
                      "scanNum: {}"
                      .format(projPath, receiver, scanNum))

                if resultsDict == {}:
                    print("Empy sparrow results dict!")
                    break

                match = compare(projPath, scanNum, resultsDict, receiver)
                numChecked += 1
                if not match:
                    bads.append((projPath, scanNum, receiver))

        print("bads: ")
        for b in bads:
            print(b)
        print("num bads", len(bads))
        print("num checked:", numChecked)


def compare(projPath, scanNum, resultsDict, receiver):

    if hasRedundantScanNums(projPath):
        print("WARNING: skipping this scan: ", projPath, scanNum)
        return True

    # try:
    if 1:
        allCal = calibrateAll(projPath, scanNum)
    # except:
    else:
        print("Something went wrong in calibrateAll")
        return False

    print(sorted(allCal.keys()))
    print(sorted(resultsDict.keys()))
    if receiver != "Rcvr26_40":
        if sorted(allCal.keys()) != sorted(resultsDict.keys()):
            print("keys are different!")
            return False
    print("&&& sparrow reults")
    for k, v in resultsDict.items():
        print(k, v[0])
    print ("&&& ")
    for k, v in allCal.items():
        mode, pol = k
        print("compare results: ", k, v[0], resultsDict[k][0])
        # if mode != 'Raw':
        if len(v[0]) != len(resultsDict[k]):
            import ipdb; ipdb.set_trace()
            print("results have different lengths")
            return False
        for ourV, sparrowV in zip(v[0], resultsDict[k]):
            tolerance = 1e-6
            # make up for the fact that sparrow rounds its (Raw, Avg)
            if mode == 'Raw' and pol == 'Avg':
                ourV = int(ourV)
            # if mode != 'DualBeam':
            if tolerance < abs(ourV - sparrowV):
                import ipdb; ipdb.set_trace()
                print("values dont' match", ourV, sparrowV)
                return False

    print(projPath, scanNum, "Results MATCH!")

    return True


if __name__ == '__main__':
    testAllResults()
    # proj = "AGBT10A-003_02"
    # path = "/home/archive/science-data/10A"
    # scanNum = 5
    # # rx = "RcvrArray18_26"
    # rx = "Rcvr1_2"
    # fn = "%s:%s:%s" % (proj, scanNum, rx)
    # fullFn = os.path.join("/home/scratch/pmargani/allCalDcrData", fn)
    # print("sparrow file", fullFn)
    # with open(fullFn, 'r') as f:
    #     sparrowResults = ast.literal_eval(f.read())
    # print("sparrow results keys: ", sparrowResults.keys())
    # for k, v in sparrowResults.items():
    #     print(k, v[0])
    # projPath = os.path.join(path, proj)
    # r = compare(projPath, scanNum, sparrowResults, rx)
    # print("Results match?", r)
