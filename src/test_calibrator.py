import ast
import unittest
import os

import numpy

from calibrator import (
    Calibrator,
    KaCalibrator,
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

    def generateAllCalibrations(self, calCls, projPath, scanNum, refBeam=None):
        """
        This function calibrates a data set using all possible calibration
        options. If "refBeam" is not specified, we assume that this receiver
        CAN'T do dual beam calibration, so we just do Raw and TotalPower.
        """
        table = decode(projPath, scanNum)

        cal = calCls(None, table)

        results = {}

        # Get the three "Raw" options, no gain processing.
        results['Raw', 'Avg'] = cal.calibrate(doGain=False)
        results['Raw', 'XL'] = cal.calibrate(doGain=False, polOption="X")
        results['Raw', 'YR'] = cal.calibrate(doGain=False, polOption="Y")
        # Get the three "TotalPower" options, which do use gain.
        results['TotalPower', 'Avg'] = cal.calibrate()
        results['TotalPower', 'XL'] = cal.calibrate(polOption="X")
        results['TotalPower', 'YR'] = cal.calibrate(polOption="Y")
        if refBeam:
            # Get the three DualBeam options
            results['DualBeam', 'Avg'] = cal.calibrate(refBeam=refBeam)
            results['DualBeam', 'XL'] = cal.calibrate(
                refBeam=refBeam, polOption="X")
            results['DualBeam', 'YR'] = cal.calibrate(
                refBeam=refBeam, polOption="Y")

        return results

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
        answers = self.generateAllCalibrations(
            WBandCalibrator, projPath, scanNum, refBeam=2)

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
        expected = readResultsFile(
            "../test/results/AGBT16B_285_01:5:Rcvr1_2")
        answers = self.generateAllCalibrations(
            TraditionalCalibrator, projPath, scanNum)

        for key in answers:
            self.assertTrue(numpy.allclose(
                answers[key], expected[key], rtol=2e-5))

    def testKaCalibrator(self):
        proj = "AGBT16A_085_06"
        projPath = ("../test/data/%s" % proj)
        scanNum = 55
        rcvr = "Rcvr26_40"

        table = decode(projPath, scanNum)

        cal = KaCalibrator(None, table)

        # get the sparrow results
        resultsFile = "%s:%s:%s" % (proj, scanNum, rcvr)
        resultsPath = os.path.join("../test/results", resultsFile)
        results = readResultsFile(resultsPath)

        # test all combos of polarizations and cal. modes
        pols = [('R', 'YR'), ('L', 'XL'), ('Both', 'Avg')]
        # TBD: currently it looks like the expected results
        # for Raw are wrong!
        # modes = [('Raw', False), ('TotalPower', True)]
        modes = [('TotalPower', True)]
        for mode, doGain in modes:
            for pol, genPol in pols:
                values = list(cal.calibrate(polOption=pol,
                                            doGain=doGain))
                expected = list(results[mode, genPol])
                self.assertEquals(values, expected)


calOpts = {
    ('Raw', 'Avg'): {
        'polOption': 'Both',
        'doGain': False,
        'refBeam': False
    },
    ('Raw', 'XL'): {
        'polOption': 'X/L',
        'doGain': False,
        'refBeam': False
    },
    ('Raw', 'YR'): {
        'polOption': 'Y/R',
        'doGain': False,
        'refBeam': False
    },
    ('TotalPower', 'Avg'): {
        'polOption': 'Both',
        'doGain': True,
        'refBeam': False
    },
    ('TotalPower', 'XL'): {
        'polOption': 'X/L',
        'doGain': True,
        'refBeam': False
    },
    ('TotalPower', 'YR'): {
        'polOption': 'Y/R',
        'doGain': True,
        'refBeam': False
    },
    ('DualBeam', 'XL'): {
        'polOption': 'X/L',
        'doGain': True,
        'refBeam': True
    },
    ('DualBeam', 'YR'): {
        'polOption': 'Y/R',
        'doGain': True,
        'refBeam': True
    },
    ('DualBeam', 'Avg'): {
        'polOption': 'Both',
        'doGain': True,
        'refBeam': True
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
            if calOption[0] == 'Raw' and calOption[1] == 'Avg':
                actual = numpy.floor(actual)

            self.assertTrue(numpy.allclose(actual, expected),
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



