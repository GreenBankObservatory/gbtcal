"""Entry point to calibration pipeline"""

import logging
import os
import numpy

from gbtcal.rcvr_table import ReceiverTable
from gbtcal.constants import CALOPTS, POLOPTS, POLS
from gbtcal.decode import decode
import gbtcal.attenuate
import gbtcal.calibrator


SCRIPTPATH = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger(__name__)

def doCalibrate(receiverTable, dataTable, calMode, polMode, calibrator=None):
    receiver = dataTable.meta['RECEIVER']
    receiverRow = receiverTable.getReceiverInfo(receiver)

    validateOptions(receiverRow, calMode, polMode)

    if polMode == POLOPTS.AVG:
        polOption = polMode
    else:
        polarizations = numpy.unique(dataTable['POLARIZE'])
        # This converts from XL/YR to X/L/Y/R
        if POLS.X in polarizations or POLS.Y in polarizations:
            polOption = polMode[0]
        elif POLS.L in polarizations or POLS.R in polarizations:
            polOption = polMode[1]
        else:
            raise ValueError("Invalid polMode '{}'; must be one of: {}"
                             .format(polMode, POLOPTS))

    # If the user has requested that we do any mode other than raw
    # it is assumed that we do attenuation
    performAttenuation = bool(calMode != CALOPTS.RAW)

    # If the user has requested that we do polarization averaging,
    # we need to enable our interPolCal
    performInterPolCal = bool(polMode == POLOPTS.AVG)

    # If the user has selected a mode that operates on two beams,
    # enable our interBeamCal
    dualBeamCalOpts = [CALOPTS.DUALBEAM, CALOPTS.BEAMSWITCHEDTBONLY]
    performInterBeamCal = bool(calMode in dualBeamCalOpts)


    # If a calibrator has been given, use it
    if calibrator:
        calibratorClass = calibrator
    # Otherwise we fall back to the default defined in the table
    else:
        # Get the calibrator as a string
        try:
            calibratorStr = receiverRow['Cal Strategy'][0]
        except IndexError:
            raise ValueError("Receiver '{}' does not exist in the receiver table!"
                             .format(receiver))
        # Get the calibrator class object from the calibrator module
        try:
            calibratorClass = getattr(gbtcal.calibrator, calibratorStr)
        except AttributeError:
            raise ValueError("Receiver {}'s indicated calibration "
                             "strategy '{}' could not be found! Please "
                             "check the receiver table to ensure it is "
                             "up to date."
                             .format(receiver, calibratorStr))

    logger.debug("Beginning calibration with calibrator: %s",
                 calibratorClass.__name__)


    calibrator = calibratorClass(
        dataTable,
        performAttenuation,
        performInterPolCal,
        performInterBeamCal
    )
    calibrator.describe()
    return calibrator.calibrate(polOption)


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


def calibrate(projPath, scanNum, calMode, polMode, rcvrTablePath=None, calibrator=None):
    if not rcvrTablePath:
        rcvrTablePath = os.path.join(SCRIPTPATH, "rcvrTable.csv")

    rcvrTable = ReceiverTable.load(rcvrTablePath)
    dataTable = decode(projPath, scanNum)

    return doCalibrate(rcvrTable, dataTable, calMode, polMode, calibrator=calibrator)


def calibrateToFile(projPath, scanNum, calMode, polMode):

    data = calibrate(projPath, scanNum, calMode, polMode)
    logger.debug("data: %s", data)
    projName = projPath.split('/')[-1]
    fn = "{}.{}.{}.{}.decode".format(projName, scanNum, calMode, polMode)
    fnp = os.path.join("/tmp", fn)
    logger.debug("data file: %s", fnp)
    with open(fnp, 'w') as f:
        f.write(str(list(data[0])))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("projdir", help="The project directory where fits data is stored (e.g. /home/gbtdata/TGBT15A_901).")
    parser.add_argument("scannum", help="The scan number for the first scan in the OOF series.", type=int)
    parser.add_argument("--calmode", help="Raw, TotalPower, or DualBeam", default='Raw')
    parser.add_argument("--polmode", help="XL, YR, Avg", default='Avg')

    # Here we provide a quick and easy way to calibrate stuff:
    args = parser.parse_args()

    # calMode = 'DualBeam'
    # polMode = 'XL'
    calibrateToFile(args.projdir, args.scannum, args.calmode, args.polmode)
    # TBF; derive from args
    # projPath = "/home/archive/science-data/11B/AGBT11B_023_02"
    # scanNum = 1
    # # projPath = '/home/archive/science-data/16B/AGBT16B_119_04'
    # projPath = '/home/archive/science-data/12A/AGBT12A_364_02'
    # # TBF: derive from receivers table
    # calModes = ["Raw", "TotalPower", "DualBeam"]
    # polModes = ["XL", "YR", "Avg"]
    # logger.debug("Calibrating scan {}, proj {}".format(scanNum, projPath))
    # for cal in calModes:
    #     for pol in polModes:
    #         logger.debug("Calibrating for {}, {}".format(cal, pol))
    #         data = calibrate(projPath, scanNum, cal, pol)
