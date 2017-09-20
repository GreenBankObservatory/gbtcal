import ast
import unittest

import numpy

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

def readResultsFile(filepath):
    with open(filepath) as f:
        stuff = ast.literal_eval(f.read())
    return stuff

class TestCalibrator(unittest.TestCase):



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

        results = readResultsFile("../test/results/AVLB17A_182_04:2:Rcvr68_92")
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


class TestRcvrPF_1(TestCalibrator):
    pass


class TestRcvrPF_2(TestCalibrator):
    pass


class TestRcvrArray1_2(TestCalibrator):
    pass

calOpts = {
    ('Raw', 'Avg'): {
        'polOption': 'Both',
        'doGain': False,
        'refBeam': False
    },
    ('Raw', 'XL'): {
        'polOption': 'X',
        'doGain': False,
        'refBeam': False
    },
    ('Raw', 'YR'): {
        'polOption': 'Y',
        'doGain': False,
        'refBeam': False
    },
    ('TotalPower', 'Avg'): {
        'polOption': 'Both',
        'doGain': True,
        'refBeam': False
    },
    ('TotalPower', 'XL'): {
        'polOption': 'X',
        'doGain': True,
        'refBeam': False
    },
    ('TotalPower', 'YR'): {
        'polOption': 'Y',
        'doGain': True,
        'refBeam': False
    }
}


class TestAgainstSparrowResults(unittest.TestCase):
    def setUp(self):
        self.receiverTable = ReceiverTable.load('rcvrTable.test.csv')

    def getScanNum(self, projPath):
        return int(projPath.split(":")[1])

    def getReceiver(self, projPath):
        return projPath.split(":")[-1]

    def arraySummary(self, array):
        return "[{} ... {}]".format(array[0], array[-1])

    def _testCalibrate(self, testDataProjName):
        projPath = "../test/data/{}".format(testDataProjName)
        scanNum = self.getScanNum(projPath)
        expectedResultsPath = "../test/results/{}".format(testDataProjName)
        expectedResults = readResultsFile(expectedResultsPath)

        table = decode(projPath, scanNum)
        receiver = self.getReceiver(projPath)

        for calOption, result in expectedResults.items():
            actual = doCalibrate(receiver, self.receiverTable, table,
                                 **calOpts[calOption])
            expected = numpy.array(result)
            # TODO: ROUNDING??? WAT
            if calOption[0] == 'Raw':
                actual = numpy.floor(actual)

            self.assertTrue(numpy.all(actual == expected),
                            "Test for {} failed: {} != {}"
                            .format(calOption,
                                    self.arraySummary(actual),
                                    self.arraySummary(expected)))

    def testRcvr1_2(self):
        self._testCalibrate("AGBT16B_285_01:1:Rcvr1_2")

    def testRcvr4_6(self):
        self._testCalibrate("AGBT17B_999_11:1:Rcvr4_6")

    def testRcvr2_3(self):
        self._testCalibrate("AGBT17A_996_01:1:Rcvr2_3")

    def testRcvr8_10(self):
        self._testCalibrate("AGBT17A_056_10:1:Rcvr8_10")

    def testRcvrArray18_26(self):
        self._testCalibrate("AGBT16B_999_118:1:RcvrArray18_26")

    def testRcvr40_52(self):
        self._testCalibrate("AGBT16A_473_01:1:Rcvr40_52")









class TestRcvr2_3(TestCalibrator):
    pass


class TestRcvr4_6(TestCalibrator):
    pass


class TestRcvr8_10(TestCalibrator):
    pass


class TestRcvr12_18(TestCalibrator):
    pass


class TestRcvrArray18_26(TestCalibrator):
    pass


class TestRcvr18_26(TestCalibrator):
    pass


class TestRcvr26_40(TestCalibrator):
    pass


class TestRcvr40_52(TestCalibrator):
    pass


class TestRcvr68_92(TestCalibrator):
    pass


class TestRcvrArray75_115(TestCalibrator):
    pass





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
