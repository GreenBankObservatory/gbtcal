from dcr_decode import decode
from rcvr_table import ReceiverTable
from calibrator import TraditionalCalibrator, WBandCalibrator, ArgusCalibrator, KaCalibrator


def calibrateDcrData(projPath, scanNum, calMode, polMode):
    rcvrTable = ReceiverTable.load("rcvrTable.csv")

    table = decode(projPath, scanNum)
    receiver = table.meta['RECEIVER']

    mask = rcvrTable['M&C Name'] == receiver

    rcvrRows = rcvrTable[mask]

    if len(rcvrRows) != 1:
        raise ValueError("There should be exactly one row in the Receiver "
                         "Table for receiver {}".format(receiver))

    rcvrRow = rcvrRows[0]

    validateOptions(rcvrRow, calMode, polMode)

    calClass = eval(rcvrRow['Calibration Strategy'])

    doGain = calMode != "Raw"
    refBeam = calMode == "DualBeam"

    calibrator = calClass(table)

    result = calibrator.calibrate(
        polOption=polMode,
        doGain=doGain,
        refBeam=refBeam
    )

    return result


def validateOptions(rcvrRow, calMode, polMode):
    calOptions = rcvrRow['Calibration Options']
    polOptions = rcvrRow['Polarization Options']
    if calMode not in calOptions:
        raise ValueError("calMode '{}' is invalid. Must be one of {}"
                          .format(calMode, calOptions))
    if polMode not in polOptions:
        raise ValueError("polMode '{}' is invalid. Must be one of {}"
                          .format(polMode, polOptions))


if __name__=="__main__":
    projPath = "../test/data/AGBT16B_285_01"
    scanNum = 5
    calMode = "Total Power"
    polMode = 'X/L'
    calibrateDcrData(projPath, scanNum, calMode, polMode)
