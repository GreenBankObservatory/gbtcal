import calibrator
from rcvr_table import ReceiverTable


def doCalibrate(receiver, receiverTable, ifDcrDataTable):
    print("Calibrating {}".format(receiver))
    receiverRow = receiverTable.getReceiverInfo(receiver)
    try:
        calibratorStr = receiverRow['Calibration Strategy'][0]
    except IndexError:
        raise ValueError("Receiver '{}' does not exist in the receiver table!"
                         .format(receiver))

    try:
        calibratorClass = getattr(calibrator, calibratorStr)
    except AttributeError:
        raise ValueError("Receiver {}'s indicated calibration "
                         "strategy '{}' could not be found! Please "
                         "check the receiver table to ensure it is "
                         "up to date."
                         .format(receiver, calibratorStr))

    calibratorClass(receiverTable, ifDcrDataTable).calibrate()


def getReceiverTable():
    return ReceiverTable.load('rcvrTable.csv')
