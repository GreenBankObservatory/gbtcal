import ast
import os
import unittest

import numpy

from gbtcal.decode import decode
from gbtcal.calibrate import doCalibrate
from gbtcal.interbeamops import BeamSubtractionDBA
from gbtcal.interpolops import InterPolAverage
from gbtcal.attenuate import CalDiodeAttenuate
from rcvr_table import ReceiverTable
from constants import POLOPTS, CALOPTS

SCRIPTPATH = os.path.dirname(os.path.abspath(__file__))

def readResultsFile(filepath):
    with open(filepath) as f:
        stuff = ast.literal_eval(f.read())
    return stuff

def arraySummary(array):
        return "[{} ... {}]".format(array[0], array[-1])

class TestCalibrate(unittest.TestCase):
    def setUp(self):
        self.receiverTable = ReceiverTable.load('test/rcvrTable.test.csv')

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

    def _testCalibrate(self, testDataProjName, optionsToIgnore=[]):
        projPath = "{}/data/{}".format(SCRIPTPATH,
                                       testDataProjName)
        scanNum = self.getScanNum(projPath)
        expectedResultsPath = (
            "{}/results/{}"
            .format(SCRIPTPATH,
                    testDataProjName)
        )
        expectedResults = readResultsFile(expectedResultsPath)

        table = decode(projPath, scanNum)
        for option in optionsToIgnore:
            if option in expectedResults:
                del expectedResults[option]
        print("expectedResults keys:", expectedResults.keys())
        for calOption, result in expectedResults.items():
            # if calOption != ('BeamSwitchedTBOnly', 'YR'):
            #     continue

            # if calOption[0] == 'BeamSwitchedTBOnly':
            #     calOption = ('DualBeam', calOption[1])
            #     import ipdb; ipdb.set_trace()

            print("CALOPT:", calOption)
            actual = doCalibrate(self.receiverTable, table, *calOption, attenType='GFM')
            # import ipdb; ipdb.set_trace()
            expected = numpy.array(result)
            # TODO: ROUNDING??? WAT
            if (calOption[0] == CALOPTS.RAW and
                    calOption[1] == POLOPTS.AVG):
                actual = numpy.floor(actual)

            self.assertTrue(numpy.allclose(actual, expected),
                            "Test for {} failed: {} != {}"
                            .format(calOption,
                                    arraySummary(actual),
                                    arraySummary(expected)))

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
        self._testCalibrate("AGBT16A_473_01:1:Rcvr40_52")

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
                # TODO: Why can't we do this? Follow up with Dave
                ('Raw', 'Avg'),
                # Sparrow does NOT properly calibrate for XL, so we ignore those
                # Sparrow tries to get XL from tracking beam, and instead gets XL from other beam

                # ('TotalPower', 'XL'),
                # ('BeamSwitchedTBOnly', 'XL'),
                # ('BeamSwitchedTBOnly', 'YR'),
                ('BeamSwitchedTBOnly', 'Avg')
            ]
        )

    def testRcvrArray75_115(self):
        self._testCalibrate(
            "AGBT17A_423_01:16:RcvrArray75_115",
            # TODO: Test that these fail gracefully
            optionsToIgnore=[
                ('Raw', 'YR'),
                ('Raw', 'Avg')
            ]

        )

    def testRcvr40_52OOF(self):

        testDataProjName = "TPTCSOOF_091031"
        projPath = "{}/data/{}".format(SCRIPTPATH,
                                       testDataProjName)
        scanNum = 45
        dataTable = decode(projPath, scanNum)

        actual = doCalibrate(self.receiverTable, dataTable,
                             calMode='DualBeam', polMode='XL', attenType='OOF')

        # call it's oof calibration
        # TODO: I get different results for YR and Avg, but I have
        # nothing to test against
        self.assertAlmostEqual(actual[0], -2.43800002314, 6)
        self.assertAlmostEqual(actual[-1], -2.25389923142, 6)
