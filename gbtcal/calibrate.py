import logging
import os
import numpy

from gbtcal.rcvr_table import ReceiverTable
from gbtcal.constants import CALOPTS, POLOPTS, ATTENTYPES
from gbtcal.decode import decode
import gbtcal.attenuate
import gbtcal.calibrate
import gbtcal.calibrator

def initLogging():
    """Initialize the logger for this module and return it"""

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


logger = initLogging()


def doCalibrate(receiverTable, dataTable, calMode, polMode, attenType):
    receiver = dataTable.meta['RECEIVER']
    receiverRow = receiverTable.getReceiverInfo(receiver)

    validateOptions(receiverRow, calMode, polMode)

    if polMode == POLOPTS.AVG:
        polOption = polMode
    else:
        # we may get 'XL', but we need to pass either 'X' or 'L'
        polarizations = numpy.unique(dataTable['POLARIZE'])
        polset = set(polarizations)
        # TODO: Dumb
        if polset.issuperset(["X"]) or polset.issuperset(["Y"]):
            polOption = polMode[0]
        elif polset.issuperset(["L"]) or polset.issuperset(["R"]):
            polOption = polMode[1]
        else:
            raise ValueError(":(")


    attenuator = None
    interPolCal = None
    interBeamCal = None

    if calMode != CALOPTS.RAW:
        # If the user has requested that we do any mode other than raw
        # it is assumed that we do attenuation

        # if attenType == ATTENTYPES.OOF:
        #     attenuatorName = receiverRow['OofAttenuator'][0]
        # else:
        attenuatorName = receiverRow['Attenuator'][0]

        if not attenuatorName:
            raise ValueError("Attenuator of type {} has not been defined for "
                             "receiver {}".format(attenType, receiver))

        attenuator = gbtcal.attenuate.get(attenuatorName)()

    if polMode == POLOPTS.AVG:
        # If the user has requested that we do polarization averaging,
        # we need to enable our interPolCal
        interPolCalName = receiverRow['InterPolCal'][0]
        interPolCal = gbtcal.interbeamops.get(interPolCalName)()

    if calMode in [CALOPTS.DUALBEAM, CALOPTS.BEAMSWITCHEDTBONLY]:
        # If the user has selected a mode that operates on two beams,
        # enable our interBeamCal
        interBeamCalName = receiverRow['InterBeamCal'][0]
        # interBeamCalName = 'OofCalibrate'
        interBeamCal = gbtcal.interbeamops.get(interBeamCalName)()

    try:
        if attenType == ATTENTYPES.OOF:
            calibratorStr = receiverRow['OofCalibrator'][0]
        else:
            calibratorStr = receiverRow['Cal Strategy'][0]
    except IndexError:
        raise ValueError("Receiver '{}' does not exist in the receiver table!"
                         .format(receiver))

    try:
        calibratorClass = getattr(gbtcal.calibrator, calibratorStr)
    except AttributeError:
        raise ValueError("Receiver {}'s indicated calibration "
                         "strategy '{}' could not be found! Please "
                         "check the receiver table to ensure it is "
                         "up to date."
                         .format(receiver, calibratorStr))

    logger.debug("Beginning calibration with calibrator %s",
                 calibratorClass.__class__.__name__)


    # polarization = polOption if polOption != POLOPTS.AVG else None
    calibrator = calibratorClass(
        dataTable,
        attenuator,
        interPolCal,
        interBeamCal
    )
    calibrator.describe()
    return calibrator.calibrate(polOption)


def validateOptions(rcvrRow, calMode, polMode):
    rcvrName = rcvrRow['M&C Name'][0]
    # calOptions = rcvrRow['Cal Options'][0]
    polOptions = rcvrRow['Pol Options'][0]
    # if calMode not in calOptions:
    #     raise ValueError("calMode '{}' is invalid for receiver {}. "
    #                      "Must be one of {}"
    #                      .format(calMode, rcvrName, calOptions))
    if polMode not in polOptions:
        raise ValueError("polMode '{}' is invalid for receiver {}. "
                         "Must be one of {}"
                         .format(polMode, rcvrName, polOptions))


def getReceiverTable():
    rcvrTableCsv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rcvrTable.csv")
    return ReceiverTable.load(rcvrTableCsv)


def calibrate(projPath, scanNum, calMode, polMode, attenType):
    rcvrTable = getReceiverTable()
    dataTable = decode(projPath, scanNum)

    return doCalibrate(rcvrTable, dataTable, calMode, polMode, attenType)


def calibrateToFile(projPath, scanNum, calMode, polMode):

    data = calibrate(projPath, scanNum, calMode, polMode)
    print("data: ", data)
    projName = projPath.split('/')[-1]
    fn = "{}.{}.{}.{}.decode".format(projName, scanNum, calMode, polMode)
    fnp = os.path.join("/tmp", fn)
    print("data file: ", fnp)
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
    # print("Calibrating scan {}, proj {}".format(scanNum, projPath))
    # for cal in calModes:
    #     for pol in polModes:
    #         print("Calibrating for {}, {}".format(cal, pol))
    #         data = calibrate(projPath, scanNum, cal, pol)
