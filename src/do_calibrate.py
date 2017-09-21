import numpy

import calibrator
from rcvr_table import ReceiverTable


def doCalibrate(receiver, receiverTable, ifDcrDataTable, **kwargs):
    print("Calibrating {}".format(receiver))
    receiverRow = receiverTable.getReceiverInfo(receiver)
    try:
        calibratorStr = receiverRow['Calibration Strategy'][0]
    except IndexError:
        raise ValueError("Receiver '{}' does not exist in the receiver table!"
                         .format(receiver))

    polarizations = numpy.unique(ifDcrDataTable['POLARIZE'])
    # import ipdb; ipdb.set_trace()
    polOpt = kwargs['polOption']
    print("polOpt: ", polOpt)
    if polOpt == 'Both':
        kwargs['polOption'] = 'Avg'
    else:
        if set(polarizations).issuperset(["X", "Y"]):
            kwargs['polOption'] = polOpt.split("/")[0]
        elif set(polarizations).issuperset(["L", "R"]):
            kwargs['polOption'] = kwargs['polOption'].split("/")[1]
        else:
            raise ValueError(":(")


    try:
        calibratorClass = getattr(calibrator, calibratorStr)
    except AttributeError:
        raise ValueError("Receiver {}'s indicated calibration "
                         "strategy '{}' could not be found! Please "
                         "check the receiver table to ensure it is "
                         "up to date."
                         .format(receiver, calibratorStr))

    return calibratorClass(receiverTable, ifDcrDataTable).calibrate(**kwargs)


def getReceiverTable():
    return ReceiverTable.load('rcvrTable.csv')
