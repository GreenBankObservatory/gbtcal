from dcr_decode import decode
from rcvr_table import ReceiverTable
from calibrator import TraditionalCalibrator, WBandCalibrator, ArgusCalibrator, KaCalibrator


def calibrateDcrData(projPath, scanNum, calMode, polMode):
    rcvrTable = ReceiverTable.load("rcvrTable.csv")
    
    table = decode(projPath, scanNum)
    receiver = table.meta['RECEIVER']

    mask = rcvrTable['M&C Name'] == receiver

    acceptableCalModes = rcvrTable.meta['calibrationOptions'].values()
    acceptablePolModes = rcvrTable.meta['calibrationOptions'].values()

    if calMode not in rcvrTable.meta['calibrationOptions'].values():
        raise ValueError("calMode {} is invalid. Must be one of {}"
                         .format(calMode, ))

    rcvrRows = rcvrTable[mask]

    if len(rcvrRows) != 1:
        raise ValueError("There should be exactly one row in the Receiver "
                         "Table for receiver {}".format(receiver))

    rcvrRow = rcvrRows[0]
    calClass = eval(rcvrRow['Calibration Strategy'])

    import ipdb; ipdb.set_trace()

    doGain = calMode != "Raw"


if __name__=="__main__":
    projPath = "../test/data/AGBT16B_285_01"
    scanNum = 5
    calMode = "Total Power"
    polMode = 'X/L'
    calibrateDcrData(projPath, scanNum, calMode, polMode)
