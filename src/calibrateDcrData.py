from dcr_decode import decode
from rcvr_table import ReceiverTable

from do_calibrate import doCalibrate


def calibrateDcrData(projPath, scanNum, calMode, polMode):
    rcvrTable = ReceiverTable.load("rcvrTable.csv")
    dataTable = decode(projPath, scanNum)

    return doCalibrate(rcvrTable, dataTable, calMode, polMode)


if __name__ == "__main__":
    projPath = "../test/data/AGBT16B_285_01:1:Rcvr1_2"
    scanNum = 1
    calMode = "Raw"
    polMode = 'Avg'
    calibrateDcrData(projPath, scanNum, calMode, polMode)
