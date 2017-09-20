import ast
import unittest

from calibrator import (
    Calibrator,
    TraditionalCalibrator,
    WBandCalibrator,
    ArgusCalibrator,
)
from do_calibrate import doCalibrate
from dcr_decode import decode
from rcvr_table import ReceiverTable
from dcr_table import DcrTable

class TestCalibrator(unittest.TestCase):

    def readResultsFile(self, filepath):
        with open(filepath) as f:
            stuff = ast.literal_eval(f.read())
        return stuff

    def testCalibrator(self):
        projPath = ("../test/data/AGBT16B_285_01")
        scanNum = 5
        table = decode(projPath, scanNum)
        c = Calibrator(None, table)
        with self.assertRaises(NotImplementedError):
            c.calibrate()

    def testWBandCalibrator(self):
        projPath = ("../test/data/AVLB17A_182_04")
        scanNum = 2
        table = decode(projPath, scanNum)
        cal = WBandCalibrator(None, table)
        values = list(cal.calibrate())

        results = self.readResultsFile("../test/results/AVLB17A_182_04:2:Rcvr68_92")
        expected = results["TotalPower", "Avg"]

        self.assertEquals(values, expected)

    def testArgusCalibrator(self):
        projPath = ("../test/data/TGBT15A_901_58")
        scanNum = 10

        table = decode(projPath, scanNum)
        cal = ArgusCalibrator(None, table)
        values = cal.calibrate()

    def testTraditionalCalibrator(self):
        projPath = ("../test/data/AGBT16B_285_01")
        scanNum = 5
        table = decode(projPath, scanNum)
        cal = TraditionalCalibrator(None, table)
        values = cal.calibrate()


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
