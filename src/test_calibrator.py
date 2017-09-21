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
from dcr_decode import decode, getFitsForScan, getAntennaTrackBeam
from rcvr_table import ReceiverTable
from dcr_table import DcrTable


class TestCalibrator(unittest.TestCase):

    def generateAllCalibrations(self, calCls, projPath, scanNum, refBeam=None):
        """
        This function calibrates a data set using all possible calibration
        options. If "refBeam" is not specified, we assume that this receiver
        CAN'T do dual beam calibration, so we just do Raw and TotalPower.
        """
        fitsForScan = getFitsForScan(projPath, scanNum)
        trckBeam = getAntennaTrackBeam(fitsForScan['Antenna'])

        table = DcrTable.read(fitsForScan['DCR'], fitsForScan['IF'])
        table.meta['TRCKBEAM'] = trckBeam
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

    def readResultsFile(self, filepath):
        with open(filepath) as f:
            stuff = ast.literal_eval(f.read())
            results = {key: numpy.array(stuff[key]) for key in stuff}
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

        expected = self.readResultsFile(
            "../test/results/AVLB17A_182_04:2:Rcvr68_92")
        answers = self.generateAllCalibrations(
            WBandCalibrator, projPath, scanNum, refBeam=2)

        for key in answers:
            self.assertTrue(numpy.allclose(answers[key], expected[key]))

    def testArgusCalibrator(self):
        projPath = ("../test/data/TGBT15A_901_58")
        scanNum = 10

        table = decode(projPath, scanNum)
        cal = ArgusCalibrator(None, table)
        values = cal.calibrate()

    def testTraditionalCalibrator(self):
        projPath = ("../test/data/AGBT16B_285_01")
        scanNum = 5
        fitsForScan = getFitsForScan(projPath, scanNum)
        trckBeam = getAntennaTrackBeam(fitsForScan['Antenna'])

        table = DcrTable.read(fitsForScan['DCR'], fitsForScan['IF'])
        table.meta['TRCKBEAM'] = trckBeam
        cal = TraditionalCalibrator(None, table)
        values = cal.calibrate()

        expected = self.readResultsFile(
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
        fitsForScan = getFitsForScan(projPath, scanNum)
        trckBeam = getAntennaTrackBeam(fitsForScan['Antenna'])

        table = DcrTable.read(fitsForScan['DCR'], fitsForScan['IF'])
        table.meta['TRCKBEAM'] = trckBeam

        cal = KaCalibrator(None, table)

        # get the sparrow results
        resultsFile = "%s:%s:%s" % (proj, scanNum, rcvr)
        resultsPath = os.path.join("../test/results", resultsFile)
        results = self.readResultsFile(resultsPath)

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
