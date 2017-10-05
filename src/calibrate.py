import numpy

import Calibrators
from rcvr_table import ReceiverTable
from constants import CALOPTS, POLOPTS
from dcr_decode import decode


def doCalibrate(receiverTable, dataTable, calMode, polMode):
    receiver = dataTable.meta['RECEIVER']
    receiverRow = receiverTable.getReceiverInfo(receiver)
    try:
        calibratorStr = receiverRow['Cal Strategy'][0]
    except IndexError:
        raise ValueError("Receiver '{}' does not exist in the receiver table!"
                         .format(receiver))

    validateOptions(receiverRow, calMode, polMode)

    if polMode == POLOPTS.AVG:
        polOption = polMode
    else:
        # we may get 'XL', but we need to pass either 'X' or 'L'
        polarizations = numpy.unique(dataTable['POLARIZE'])
        polset = set(polarizations)
        if polset.issuperset(["X"]) or polset.issuperset(["Y"]):
            polOption = polMode[0]
        elif polset.issuperset(["L"]) or polset.issuperset(["R"]):
            polOption = polMode[1]
        else:
            raise ValueError(":(")

    doGain = calMode != CALOPTS.RAW
    refBeam = calMode == CALOPTS.DUALBEAM or calMode == CALOPTS.BEAMSWITCHEDTBONLY

    try:
        calibratorClass = getattr(Calibrators, calibratorStr)
    except AttributeError:
        raise ValueError("Receiver {}'s indicated calibration "
                         "strategy '{}' could not be found! Please "
                         "check the receiver table to ensure it is "
                         "up to date."
                         .format(receiver, calibratorStr))

    return calibratorClass(dataTable).calibrate(polOption, doGain, refBeam)


def validateOptions(rcvrRow, calMode, polMode):
    rcvrName = rcvrRow['M&C Name'][0]
    calOptions = rcvrRow['Cal Options'][0]
    polOptions = rcvrRow['Pol Options'][0]
    if calMode not in calOptions:
        raise ValueError("calMode '{}' is invalid for receiver {}. "
                         "Must be one of {}"
                         .format(calMode, rcvrName, calOptions))
    if polMode not in polOptions:
        raise ValueError("polMode '{}' is invalid for receiver {}. "
                         "Must be one of {}"
                         .format(polMode, rcvrName, polOptions))


def getReceiverTable():
    return ReceiverTable.load('rcvrTable.csv')


def calibrate(projPath, scanNum, calMode, polMode):
    rcvrTable = getReceiverTable()
    dataTable = decode(projPath, scanNum)

    return doCalibrate(rcvrTable, dataTable, calMode, polMode)


if __name__ == "__main__":

    # Here we provide a quick and easy way to calibrate stuff:

    # TBF; derive from args
    # projPath = "/home/archive/science-data/11B/AGBT11B_023_02"
    scanNum = 1
    projPath = '/home/archive/science-data/16B/AGBT16B_119_04'
    # TBF: derive from receivers table
    calModes = ["Raw", "TotalPower", "DualBeam"]
    polModes = ["XL", "YR", "Avg"]
    print("Calibrating scan {}, proj {}".format(scanNum, projPath))
    for cal in calModes:
        for pol in polModes:
            print("Calibrating for {}, {}".format(cal, pol))
            data = calibrate(projPath, scanNum, cal, pol)
