import unittest
import os

from calibrator import (
    Calibrator,
    KaCalibrator,
    TraditionalCalibrator,
    WBandCalibrator,
    ArgusCalibrator,
)
from do_calibrate import doCalibrate
from dcr_decode_astropy import getFitsForScan, getAntennaTrackBeam
from rcvr_table import ReceiverTable
from dcr_table import DcrTable

class TestCalibrator(unittest.TestCase):

    def readResultsFile(self, filepath):
        with open(filepath) as f:
            stuff = eval(f.read())
        return stuff

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

    def testWBandCalibrator(self):
        projPath = ("../test/data/AVLB17A_182_04")
        scanNum = 2
        fitsForScan = getFitsForScan(projPath, scanNum)
        trckBeam = getAntennaTrackBeam(fitsForScan['Antenna'])

        table = DcrTable.read(fitsForScan['DCR'], fitsForScan['IF'])
        table.meta['TRCKBEAM'] = trckBeam
        cal = WBandCalibrator(None, table)
        values = list(cal.calibrate())

        results = self.readResultsFile("../test/results/AVLB17A_182_04:2:Rcvr68_92")
        expected = results["TotalPower", "Avg"]

        self.assertEquals(values, expected)

    def testArgusCalibrator(self):
        projPath = ("../test/data/TGBT15A_901_58")
        scanNum = 10
        fitsForScan = getFitsForScan(projPath, scanNum)
        trckBeam = getAntennaTrackBeam(fitsForScan['Antenna'])

        table = DcrTable.read(fitsForScan['DCR'], fitsForScan['IF'])
        table.meta['TRCKBEAM'] = trckBeam
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
                expected = results[mode, genPol]
                self.assertEquals(values, expected)

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
