import unittest

from calibrator import (
    Calibrator,
    TraditionalCalibrator,
    InvalidCalibrator,
    WBandCalibrator,
    ArgusCalibrator,
)

from do_calibrate import (
    doCalibrate,
    getReceiverTable
)

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
        tc = TraditionalCalibrator(None, None)

    def testInvalidCalibrator(self):
        ic = InvalidCalibrator(None, None)
        with self.assertRaises(NotImplementedError):
            ic.calibrate(None)

class TestDoCalibrate(unittest.TestCase):
    def setUp(self):
        print("\n")
        self.receiverTable = ReceiverTable.load('rcvrTable.csv')

    def testAll(self):
        for receiver in self.receiverTable['M&C Name']:
            print
            doCalibrate(receiver, self.receiverTable, None)

    def testInvalidReceiver(self):
        with self.assertRaises(ValueError):
            doCalibrate('fake!', self.receiverTable, None)
