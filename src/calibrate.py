import logging
import os
import numpy

import newcalibrator
from rcvr_table import ReceiverTable
from constants import CALOPTS, POLOPTS, ATTENTYPES
from dcr_decode import decode
import attenuate
import newcalibrate

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
        if polset.issuperset(["X"]) or polset.issuperset(["Y"]):
            polOption = polMode[0]
        elif polset.issuperset(["L"]) or polset.issuperset(["R"]):
            polOption = polMode[1]
        else:
            raise ValueError(":(")


    attenuator = None
    interPolCal = None
    interBeamCal = None
    queryParams = {}

    if calMode != CALOPTS.RAW:
        # If the user has requested that we do any mode other than raw
        # it is assumed that we do attenuation

        if attenType == ATTENTYPES.OOF:
            attenuatorName = receiverRow['OofAttenuator'][0]
        else:
            attenuatorName = receiverRow['Attenuator'][0]

        if not attenuatorName:
            raise ValueError("Attenuator of type {} has not been defined for "
                             "receiver {}".format(attenType, receiver))

        attenuator = getattr(attenuate, attenuatorName)()


    if polMode == POLOPTS.AVG:
        # If the user has requested that we do polarization averaging,
        # we need to enable our interPolCal
        interPolCalName = receiverRow['InterPolCal'][0]
        interPolCal = getattr(newcalibrate, interPolCalName)()
    else:
        # Otherwise we set polarize to the parsed polMode, polOption.
        # So, it will be one of X, Y, R, or L. Since we are not
        # averaging pols, we will instead be simply selecting a
        # polarization -- this is the one to select
        queryParams['POLARIZE'] = polOption

    if calMode in [CALOPTS.DUALBEAM, CALOPTS.BEAMSWITCHEDTBONLY]:
        # If the user has selected a mode that operates on two beams,
        # enable our interBeamCal
        interBeamCalName = receiverRow['InterBeamCal'][0]
        # interBeamCalName = 'OofCalibrate'
        interBeamCal = getattr(newcalibrate, interBeamCalName)()
    # else:
        # Otherwise we set feed to the track beam. This is the signal
        # beam, and it is what we care about when doing total power, etc.
        # InterBeamCal needs two beams; here we only need one
        # queryParams['FEED'] = dataTable.meta['TRCKBEAM']

    # Filter the table based on the above query parameters. If none
    # are given, we'll just keep the whole table
    filteredTable = dataTable.query(**queryParams)

    logger.debug("Raw IF/DCR data table:\n%s", dataTable)
    logger.debug("Filtering based on parameters: %s", queryParams)
    logger.debug("Filtered IF/DCR data table:\n%s", filteredTable)


    try:
        calibratorStr = receiverRow['Cal Strategy'][0]
    except IndexError:
        raise ValueError("Receiver '{}' does not exist in the receiver table!"
                         .format(receiver))

    try:
        calibratorClass = getattr(newcalibrator, calibratorStr)
    except AttributeError:
        raise ValueError("Receiver {}'s indicated calibration "
                         "strategy '{}' could not be found! Please "
                         "check the receiver table to ensure it is "
                         "up to date."
                         .format(receiver, calibratorStr))

    logger.debug("Beginning calibration with calibrator %s",
                 calibratorClass.__class__.__name__)


    return calibratorClass(
        filteredTable,
        attenuator,
        interPolCal,
        interBeamCal
    ).calibrate()


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
    return ReceiverTable.load('rcvrTable.csv')


def calibrate(projPath, scanNum, calMode, polMode):
    rcvrTable = getReceiverTable()
    dataTable = decode(projPath, scanNum)

    # make TraditionalCalibrator object
    # cal = Calibrators.TraditionalCalibrator(dataTable)

    # call it's oof calibration
    # return cal.calibrateOOF(polMode)

    return doCalibrate(rcvrTable, dataTable, calMode, polMode)


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
    projPath = args.projdir
    scanNum = args.scannum
    calMode = args.calmode
    polMode = args.polmode

    # calMode = 'DualBeam'
    # polMode = 'XL'
    calibrateToFile(projPath, scanNum, calMode, polMode)
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
