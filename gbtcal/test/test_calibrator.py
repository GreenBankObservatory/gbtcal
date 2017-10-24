import ast
import logging
import os
import unittest

import numpy

from gbtcal.calibrate import calibrate
from gbtcal.interbeamops import BeamSubtractionDBA
from gbtcal.interpolops import InterPolAverage
from gbtcal.attenuate import CalDiodeAttenuate
from gbtcal.rcvr_table import ReceiverTable
from gbtcal.constants import POLOPTS, CALOPTS

from gbtcal.calibrator import TraditionalOofCalibrator

logger = logging.getLogger(__name__)

SCRIPTPATH = os.path.dirname(os.path.abspath(__file__))
rcvrTablePath = os.path.join(SCRIPTPATH, "rcvrTable.test.csv")

def readResultsFile(filepath):
    with open(filepath) as f:
        stuff = ast.literal_eval(f.read())
    return stuff

def arraySummary(array):
        return "[{} ... {}]".format(array[0], array[-1])

class TestCalibrate(unittest.TestCase):
    def setUp(self):
        self.receiverTable = ReceiverTable.load('{}/rcvrTable.test.csv'
                                                .format(SCRIPTPATH))

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

        for option in optionsToIgnore:
            if option in expectedResults:
                del expectedResults[option]
        logger.info("Preparing to execute the following tests: %s",
                    expectedResults.keys())
        for calOption, result in expectedResults.items():
            # NOTE: Uncomment this to run only a specific type of test
            # if calOption != ('BeamSwitchedTBOnly', 'YR'):
            #     continue

            logger.info("Executing test of: %s", calOption)
            calMode = calOption[0]
            polMode = calOption[1]
            actual = calibrate(projPath, scanNum, calMode, polMode,
                               rcvrTablePath=rcvrTablePath)
            expected = numpy.array(result)
            if (calOption[0] == CALOPTS.RAW and
                    calOption[1] == POLOPTS.AVG):
                # NOTE: We must round here to match what Sparrow does.
                # We have decided that our method is more accurate.
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
                # We don't do this because it isn't scientifically
                # useful to average polarizations for Ka -- they
                # exist in different beams, and thus look at different parts
                # of the sky (at any given time, at least)
                ('Raw', 'Avg'),
                ('BeamSwitchedTBOnly', 'Avg'),


                # Sparrow does NOT properly calibrate for XL, so we ignore those
                # Sparrow tries to get XL from tracking beam, and instead gets XL from other beam

                # ('TotalPower', 'XL'),
                ('BeamSwitchedTBOnly', 'XL'),
                # ('BeamSwitchedTBOnly', 'YR'),
                # 
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
