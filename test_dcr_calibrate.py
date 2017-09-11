import os

from dcr_calibrate import calibrateAll


def testAllResults():

    sparrow_results_dir = '/home/scratch/pmargani/allCalDcrData'

    dataSrcDctFn = "/users/pmargani/tmp/rcvrDCRscans.txt"
    with open(dataSrcDctFn, 'r') as f:
        dataSrcDct = eval(f.read())

    skipRcvrs = ["Rcvr68_92", "RcvrArray75_115", 'Rcvr26_40', 'Rcvr12_18', 'Rcvr18_26']

    for receiver, projInfos in dataSrcDct.items():
        print("receiver", receiver)

        if receiver in skipRcvrs:
            print("cant process rcvr", receiver)
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

        for projInfo in projInfosFlat[:1]:
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
                        resultsDict = eval(f.read())
                except IOError as e:
                    print(e)
                    print("Could not find sparrow results file {}"
                          .format(sparrow_results_file))
                    break

                print("projPath: {}\n"
                      "receiver: {}\n"
                      "scanNum: {}"
                      .format(projPath, receiver, scanNum))

                compare(projPath, scanNum, resultsDict)


def compare(projPath, scanNum, resultsDict):
    allCal = calibrateAll(projPath, scanNum)
    print(sorted(allCal.keys()))
    print(sorted(resultsDict.keys()))
    assert sorted(allCal.keys()) == sorted(resultsDict.keys())
    print("sparrow reults")
    for k, v in resultsDict.items():
        print(k, v[0])
    for k, v in allCal.items():
        mode, pol = k
        print(k, v[0], resultsDict[k][0])
        # if mode != 'Raw':
        assert len(v) == len(resultsDict[k])
        for ourV, sparrowV in zip(v, resultsDict[k]):
            tolerance = 1e-6
            if mode == 'Raw' and pol == 'Avg':
                ourV = int(ourV)
            assert tolerance > abs(ourV - sparrowV)


if __name__ == '__main__':
    testAllResults()
