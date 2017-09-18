import unittest

from calibrator import (
    Calibrator,
    TraditionalCalibrator,
    InvalidCalibrator,
    WBandCalibrator,
    ArgusCalibrator,
)
from do_calibrate import doCalibrate
from dcr_decode_astropy import getDcrDataMap
from rcvr_table import ReceiverTable

class TestCalibrator(unittest.TestCase):
    def testCalibrator(self):
        c = Calibrator(None, None)
        with self.assertRaises(NotImplementedError):
            c.calibrate(None)

    def testWBandCalibrator(self):
        wc = WBandCalibrator(None, None)

    def testArgusCalibrator(self):
        ac = ArgusCalibrator(None, None)

    def testTraditionalCalibrator(self):
        projPath = ("/home/gbtdata/AGBT16B_285_01")
        scanNum = 5
        table = getDcrDataMap(projPath, scanNum)
        tc = TraditionalCalibrator(None, table)
        values = tc.calibrate()
        import ipdb; ipdb.set_trace()

    def testInvalidCalibrator(self):
        ic = InvalidCalibrator(None, None)
        with self.assertRaises(NotImplementedError):
            ic.calibrate(None)

class TestDoCalibrate(unittest.TestCase):
    def setUp(self):
        self.receiverTable = ReceiverTable.load('rcvrTable.test.csv')


    def testAll(self):
        for receiver in self.receiverTable['M&C Name']:
            print
            doCalibrate(receiver, self.receiverTable, None)

    def testInvalidReceiver(self):
        with self.assertRaises(ValueError):
            doCalibrate('fake!', self.receiverTable, None)
