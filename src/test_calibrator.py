import ast
import unittest

import numpy

from Calibrators import (
    Calibrator,
    KaCalibrator,
    TraditionalCalibrator,
    WBandCalibrator,
    ArgusCalibrator,
)
from calibrate import doCalibrate
from dcr_decode import decode
from rcvr_table import ReceiverTable
from constants import POLOPTS, CALOPTS


def readResultsFile(filepath):
    with open(filepath) as f:
        stuff = ast.literal_eval(f.read())
    return stuff


class TestAgainstSparrowResults(unittest.TestCase):
    def setUp(self):
        self.receiverTable = ReceiverTable.load('rcvrTable.test.csv')

    def getScanNum(self, testProjPath):
        """Given a test project path, derive the scan number and return it.
        testProjPath must be of the format:
        "<projName>:<scanNum>:<receiver>" or a ValueError will be raised
        """
        decomposedPath = testProjPath.split(":")
        if len(decomposedPath) != 3:
            raise ValueError("testProjPath must be of the format "
                             "<projName>:<scanNum>:<receiver>; got {}"
                             .format(testProjPath))

        return int(decomposedPath[1])

    def getReceiver(self, testProjPath):
        """Given a test project path, derive the receiver and return it.
        testProjPath must be of the format:
        "<projName>:<scanNum>:<receiver>" or a ValueError will be raised
        """
        decomposedPath = testProjPath.split(":")
        if len(decomposedPath) != 3:
            raise ValueError("testProjPath must be of the format "
                             "<projName>:<scanNum>:<receiver>; got {}"
                             .format(testProjPath))
        return decomposedPath[2]

    def arraySummary(self, array):
        return "[{} ... {}]".format(array[0], array[-1])

    def _testCalibrate(self, testDataProjName, optionsToIgnore=[]):
        projPath = "../test/data/{}".format(testDataProjName)
        scanNum = self.getScanNum(projPath)
        expectedResultsPath = "../test/results/{}".format(testDataProjName)
        expectedResults = readResultsFile(expectedResultsPath)

        table = decode(projPath, scanNum)
        for option in optionsToIgnore:
            if option in expectedResults:
                del expectedResults[option]
        for calOption, result in expectedResults.items():
            actual = doCalibrate(self.receiverTable, table,
                                 *calOption)
            expected = numpy.array(result)
            # TODO: ROUNDING??? WAT
            if (calOption[0] == CALOPTS.RAW and
                    calOption[1] == POLOPTS.AVG):
                actual = numpy.floor(actual)
            self.assertTrue(numpy.allclose(actual, expected),
                            "Test for {} failed: {} != {}"
                            .format(calOption,
                                    self.arraySummary(actual),
                                    self.arraySummary(expected)))

    def testRcvr1_2(self):
        """Test L Band"""
        self._testCalibrate("AGBT16B_285_01:1:Rcvr1_2")

    def testRcvr2_3(self):
        """Test S Band"""
        self._testCalibrate("AGBT17A_996_01:1:Rcvr2_3")

    def testRcvr4_6(self):
        """Test C Band"""
        self._testCalibrate("AGBT17B_999_11:1:Rcvr4_6")

    def testRcvr8_10(self):
        """Test X Band"""
        self._testCalibrate("AGBT17A_056_10:1:Rcvr8_10")

    def testRcvrArray18_26(self):
        """Test KFPA"""
        self._testCalibrate("AGBT16B_999_118:1:RcvrArray18_26")

    def testRcvr40_52(self):
        """Test Q Band"""
        # TODO: Figure out why we are excluding DualBeam from here.
        self._testCalibrate(
            "AGBT16A_473_01:1:Rcvr40_52",
            optionsToIgnore=[
                ('DualBeam', 'XL'), ('DualBeam', 'YR'), ('DualBeam', 'Avg')
            ]
        )

    def testRcvr68_92(self):
        """Test W Band"""
        # TODO: DualBeam not being tested here.
        self._testCalibrate("AVLB17A_182_04:2:Rcvr68_92")

    def testRcvr26_40(self):
        """Test Ka Band"""
        # TODO: Figure out if it makes any sense to include Avg in here.
        self._testCalibrate(
            "AGBT16A_085_06:55:Rcvr26_40",
            optionsToIgnore=[
                ('Raw', 'Avg'),
                # Sparrow does NOT properly calibrate for XL, so we ignore those
                ('BeamSwitchedTBOnly', 'XL'),
                ('BeamSwitchedTBOnly', 'Avg')
            ]
        )

    def testRcvr75_115(self):
        pass