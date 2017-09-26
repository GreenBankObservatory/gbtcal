import numpy

import Calibrators
from rcvr_table import ReceiverTable
from constants import CALOPTS, POLOPTS
from dcr_decode import decode


def doCalibrate(receiverTable, dataTable, calMode, polMode):
    receiver = dataTable.meta['RECEIVER']
    receiverRow = receiverTable.getReceiverInfo(receiver)
    try:
        calibratorStr = receiverRow['Calibration Strategy'][0]
    except IndexError:
        raise ValueError("Receiver '{}' does not exist in the receiver table!"
                         .format(receiver))

    validateOptions(receiverRow, calMode, polMode)

    if polMode == POLOPTS.AVG:
        polOption = polMode
    else:
        polarizations = numpy.unique(dataTable['POLARIZE'])
        if set(polarizations).issuperset(["X", "Y"]):
            polOption = polMode[0]
        elif set(polarizations).issuperset(["L", "R"]):
            polOption = polMode[1]
        else:
            raise ValueError(":(")

    doGain = calMode != CALOPTS.RAW
    refBeam = calMode == CALOPTS.DUALBEAM

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
    calOptions = rcvrRow['Calibration Options'][0]
    polOptions = rcvrRow['Polarization Options'][0]
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
