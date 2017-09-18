import unittest

from calibrator import (
    Calibrator,
    TraditionalCalibrator,
    WBandCalibrator,
    ArgusCalibrator,
)
from do_calibrate import doCalibrate
from dcr_decode_astropy import getFitsForScan, getAntennaTrackBeam
from rcvr_table import ReceiverTable
from dcr_table import DcrTable

class TestCalibrator(unittest.TestCase):
    def testCalibrator(self):
        projPath = ("../test/data/AGBT16B_285_01")
        scanNum = 5
        fitsForScan = getFitsForScan(projPath, scanNum)
        trckBeam = getAntennaTrackBeam(fitsForScan['Antenna'])

        table = DcrTable.read(fitsForScan['DCR'], fitsForScan['IF'])
        table.meta['TRCKBEAM'] = trckBeam
        c = Calibrator(None, table)
        with self.assertRaises(NotImplementedError):
            c.calibrate()

    # def testWBandCalibrator(self):
    #     wc = WBandCalibrator(None, None)

    # def testArgusCalibrator(self):
    #     ac = ArgusCalibrator(None, None)

    def testTraditionalCalibrator(self):
        projPath = ("../test/data/AGBT16B_285_01")
        scanNum = 5
        fitsForScan = getFitsForScan(projPath, scanNum)
        trckBeam = getAntennaTrackBeam(fitsForScan['Antenna'])

        table = DcrTable.read(fitsForScan['DCR'], fitsForScan['IF'])
        table.meta['TRCKBEAM'] = trckBeam
        tc = TraditionalCalibrator(None, table)
        values = tc.calibrate()
        # import ipdb; ipdb.set_trace()


# class TestDoCalibrate(unittest.TestCase):
#     def setUp(self):
#         self.receiverTable = ReceiverTable.load('rcvrTable.test.csv')

#     # def testRcvr1_2(self):
#     #     projPath =
#     #     table = getDcrDataMap(projPath, scanNum)
#     #     doCalibrate(receiver, self.receiverTable, table)

#     def testAll(self):
#         for receiver in self.receiverTable['M&C Name']:
#             print
#             doCalibrate(receiver, self.receiverTable, None)

#     def testInvalidReceiver(self):
#         with self.assertRaises(ValueError):
#             doCalibrate('fake!', self.receiverTable, None)
