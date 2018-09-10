"""Entry point to calibration pipeline"""

from __future__ import print_function
import argparse
import logging
import os
import sys

import numpy

from gbtcal.rcvr_table import ReceiverTable
from gbtcal.constants import CALOPTS, POLOPTS, POLS
from gbtcal.decode import decode
import gbtcal.converter
import gbtcal.calibrator


SCRIPTPATH = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger(__name__)


def doCalibrate(receiverTable, dataTable, calMode, polMode, calibrator=None, **kwargs):
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
    performConversion = bool(calMode != CALOPTS.RAW)

    # If the user has requested that we do polarization averaging,
    # we need to enable our interPolCal
    performInterPolOp = bool(polMode == POLOPTS.AVG)

    # If the user has selected a mode that operates on two beams,
    # enable our interBeamCal
    dualBeamCalOpts = [CALOPTS.DUALBEAM, CALOPTS.BEAMSWITCHEDTBONLY]
    performInterBeamOp = bool(calMode in dualBeamCalOpts)


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
        performConversion,
        performInterPolOp,
        performInterBeamOp,
        **kwargs
    )
    calibrator.describe()
    return calibrator.calibrate(polOption)


def validateOptions(rcvrRow, calMode, polMode):
    """Validate given calMode and polMode against those in the given receiver table row"""
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


def calibrate(projPath, scanNum, calMode, polMode,
              rcvrTablePath=None, calibrator=None, calseq=True):
    """Decode the IF/DCR table for given project path and scan, then calibrate"""

    if not rcvrTablePath:
        rcvrTablePath = os.path.join(SCRIPTPATH, "rcvrTable.csv")

    # Load the receiver table from the rcvrTable.csv
    rcvrTable = ReceiverTable.load(rcvrTablePath)
    # Decode the IF/DCR data table for the given scan
    dataTable = decode(projPath, scanNum)

    # Pass these on to doCalibrate
    return doCalibrate(rcvrTable, dataTable, calMode, polMode,
                       calibrator=calibrator, calseq=calseq)


def parseArgs():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-V", "--version", action="store_true")
    args = parser.parse_args()
    if args.version:
        from gbtcal import __version__
        print(__version__)
        sys.exit(0)

    parser.add_argument("projpath",
                        help="The project directory where fits data is "
                             "stored (e.g. /home/gbtdata/TGBT15A_901).")
    parser.add_argument("scan",
                        help="The scan number for the first scan in "
                        "the OOF series.",
                        type=int)
    parser.add_argument("--calmode",
                        choices=CALOPTS.all(),
                        help="A GFM-style calibration mode",
                        default=CALOPTS.RAW)
    parser.add_argument("--polmode",
                        choices=POLOPTS.all(),
                        help="A GFM-style polarization mode",
                        default=POLOPTS.AVG)
    parser.add_argument("-v", "--verbose",
                        action="store_true")
    parser.add_argument("-n", "--nocalseq",
                        help="Do not use calseq scans to determine gains.  "
                             "Use gains = 1.0.  "
                             "For only receivers like W-band and Argus.",
                        action="store_true")
    parser.add_argument("-o", "--output",
                        help="The output path to save the calibrated data. "
                             "Note that this uses numpy.savetxt, and will "
                             "result in a file in which each index is saved "
                             "to its own line")




    return parser.parse_args()


def main():
    args = parseArgs()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    data = calibrate(args.projpath, args.scan, args.calmode, args.polmode,
                     calseq=not args.nocalseq)
    print("Calibrated data:")
    print(data)
    if args.output:
        print("Saving calibrated data to {}".format(args.output))
        numpy.savetxt(args.output, data)


if __name__ == "__main__":
    main()
