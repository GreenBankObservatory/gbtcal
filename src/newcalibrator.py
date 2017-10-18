import logging
import os

from astropy.table import Column

from astropy.io import fits
import numpy

from constants import POLS, POLOPTS, CALOPTS
from dcr_decode import getFitsForScan, getTcal, getRcvrCalTable
from util import wprint
from querytable import QueryTable
# from Calibrators import TraditionalCalibrator

from WBandCalibration import WBandCalibration

from ArgusCalibration import ArgusCalibration


def initLogging():
    """Initialize the logger for this module and return it"""

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


logger = initLogging()

class Calibrator(object):
    def __init__(self, table,
                 attenuator=None,
                 interPolCalibrator=None,
                 interBeamCalibrator=None):
        self.table = table.copy()
        self.projPath = table.meta['PROJPATH']
        self.scanNum = table.meta['SCAN']
        self.attenuator = attenuator
        self.interPolCalibrator = interPolCalibrator
        self.interBeamCalibrator = interBeamCalibrator

        self.table.add_column(
            Column(name='FACTOR',
                   dtype=numpy.float64,
                   data=numpy.ones(len(self.table))
            )
        )

        self.describe()

    def describe(self):
        logger.info("My name is %s", self.__class__.__name__)
        logger.info("I will be calibrating this data:\n%s",
                    self.table)

        if self.attenuator:
            logger.info("I will perform attenuation using: %s",
                        self.attenuator.__class__.__name__)
        else:
            logger.info("I will perform NO attenuation")

        if self.interPolCalibrator:
            logger.info("I will perform inter-pol calibration using: %s",
                        self.interPolCalibrator.__class__.__name__)
        else:
            logger.info("I will perform NO inter-pol calibration")

        if self.interBeamCalibrator:
            logger.info("I will perform inter-beam calibration using: %s",
                        self.interBeamCalibrator.__class__.__name__)
        else:
            logger.info("I will perform NO inter-beam calibration")

    def initCalTable(self):
        calTable = QueryTable(self.table.getUnique(['FEED', 'POLARIZE']))
        calTable.add_column(Column(name='DATA',
                                   length=len(calTable),
                                   dtype=numpy.float64,
                                   shape=self.table['DATA'].shape[1]))

        return calTable

    def initFeedTable(self, calTable):
        feedTable = QueryTable([numpy.unique(calTable['FEED'])])
        feedTable.add_column(Column(name='DATA',
                                    length=len(feedTable),
                                    dtype=numpy.float64,
                                    shape=calTable['DATA'].shape[1]))

        return feedTable

    def findCalFactors(self):
        raise NotImplementedError("findCalFactors() must be implemented for "
                                  "all Calibrator subclasses!")

    def attenuate(self, calTable):
        # Populate FACTORS column with calibration factors (in place)
        self.findCalFactors()

        for factor in self.table.getUnique('FACTOR'):
            dataToAttenuate = self.table.query(FACTOR=factor)
            feed = dataToAttenuate['FEED'][0]
            pol = dataToAttenuate['POLARIZE'][0]
            mask = (
                (calTable['FEED'] == feed) &
                (calTable['POLARIZE'] == pol)
            )
            power = self.attenuator.attenuate(dataToAttenuate)
            calTable['DATA'][mask] = power

        return calTable

    # def attenuate(self, calTable):
    #     self.findCalFactors()

    #     return self.attenuator.attenuate(self.table, calTable)

    def interPolCalibrate(self, feedTable, calTable):
        for row in feedTable:
            feedMask = calTable['FEED'] == row['FEED']
            filteredCalTable = calTable[feedMask]
            row['DATA'] = self.interPolCalibrator.calibrate(filteredCalTable)

    def interBeamCalibrate(self, sigFeedData, refFeedData):
        return self.interBeamCalibrator.calibrate(sigFeedData, refFeedData)

    def calibrate(self):
        calTable = self.initCalTable()
        logger.debug("Initialized calTable:\n%s", calTable)
        if self.attenuator:
            # If we have an attenuator, then use it. This will
            # attenuate the data and populate the calData DATA column
            logger.info("Attenuating...")
            self.attenuate(calTable)
        else:
            # If not, we just remove all of our rows that have data
            # taking while the cal diode was on
            logger.info("Removing 'cal on' data...")
            calTable['DATA'] = self.table.query(CAL=0)['DATA']
        logger.debug("After cal data processing:\n%s", calTable)

        # So, we now have a calData table with a populated DATA column,
        # ready for the next stage

        feedTable = self.initFeedTable(calTable)
        logger.debug("Initialized feed table:\n%s", feedTable)
        if self.interPolCalibrator:
            # If we have an inter-pol calibrator, then use it. This will
            # calibrate the data between the two polarizations in the
            # calTable and store the results by feed in feedTable
            logger.debug("Performing inter-polarization calibration "
                         "using calibrator %s",
                         self.interPolCalibrator.__class__.__name__)
            self.interPolCalibrate(feedTable, calTable)

        # NOTE: If we don't have an interPolCalibrator, we just do
        # nothing -- we expect that the proper filtering has already
        # been done upstream
        # TODO: Prove that this is true!
        else:
            # logger.debug("Copying calTable")
            feedTable['DATA'] = calTable['DATA']

            # self.getSigFeedData(feedTable, calTable)

        logger.debug("Feed table is now:\n%s", feedTable)

        # import ipdb; ipdb.set_trace()
        sigFeed = self.table.meta['TRCKBEAM']
        if self.interBeamCalibrator:
            logger.debug("Performing inter-beam calibration using "
                         "calibrator %s",
                         self.interBeamCalibrator.__class__.__name__)

            refFeed = self.table[self.table['FEED'] != sigFeed]['FEED'][0]
            data = self.interBeamCalibrate(self.table, calTable)
            # data = self.interBeamCalibrate(feedTable.query(FEED=sigFeed)['DATA'],
            #                                feedTable.query(FEED=refFeed)['DATA'])
            # import ipdb; ipdb.set_trace()
        else:
            # TODO: I suspect that this is a no-op...
            # TODO: But it seems essential...
            logger.debug("Removing non-signal-feed data")
            data = feedTable[feedTable['FEED'] == sigFeed]['DATA']
            # data = feedTable['DATA'][0]
        logger.debug("Feed table is now:\n%s", feedTable)
        logger.debug("Final calibrated data:\n%s", data)
        return data

class TraditionalCalibrator(Calibrator):
    def findCalFactors(self):
        table = self.table
        receiver = table.meta['RECEIVER']

        fitsForScan = getFitsForScan(self.projPath, self.scanNum)
        rcvrCalHduList = fitsForScan[receiver]
        rcvrCalTable = getRcvrCalTable(rcvrCalHduList)

        # TODO: Double check this assumption
        uniqueRows = numpy.unique(table['FEED', 'POLARIZE',
                                       'CENTER_SKY', 'BANDWDTH',
                                       'HIGH_CAL'])
        for feed, pol, centerSkyFreq, bandwidth, highCal in uniqueRows:
            mask = (
                (table['FEED'] == feed) &
                (table['POLARIZE'] == pol) &
                (table['CENTER_SKY'] == centerSkyFreq) &
                (table['BANDWDTH'] == bandwidth) &
                (table['HIGH_CAL'] == highCal)
            )

            maskedTable = table[mask]

            if len(numpy.unique(maskedTable['RECEPTOR'])) != 1:
                raise ValueError("The rows in the receiver calibration file "
                                 "must all be unique for all "
                                 "feed/polarization/frequency groupings.")

            receptor = maskedTable['RECEPTOR'][0]

            tCal = getTcal(rcvrCalTable, feed, receptor, pol,
                           highCal, centerSkyFreq, bandwidth)
            table['FACTOR'][mask] = tCal

class CalSeqCalibrator(Calibrator):
    # def __init__(self, *args, **kwargs):
    #     super(CalSeqCalibrator, self).__init__(*args, **kwargs)
    #     self.attenuator = None


    def findCalFactors(self):
        table = self.table
        # This is defined in the subclasses
        gains = self.getGains()
        if gains is None:
            # We didn't find the gains, so we want to keep FACTOR values 1.0
            wprint("Could not find gain values. Setting all gains to 1.0")
            return

        # table['FACTOR']
        # import ipdb; ipdb.set_trace()
        for row in table:
            index = str(row['FEED']) + row['POLARIZE']
            # print(index)
            row['FACTOR'] = gains[index]

    def getGains(self):
        raise NotImplementedError("getGains must be implemented by all "
                                  "CalSeqCalibrator subclasses")

    def _getScanProcedures(self):
        """Return a list of each scan number and its procname"""
        # projName = projPath.split('/')[-1]
        path = "/".join(self.projPath.split('/')[:-1])

        scanLog = fits.getdata(os.path.join(self.projPath, "ScanLog.fits"))
        scans = []
        for row in scanLog:
            _, scan, filepath = row
            if 'GO' in filepath:
                goFile = os.path.join(path, filepath)
                try:
                    goHdu = fits.open(goFile)
                    h = goHdu[0].header
                    scans.append(
                        (scan, h['PROCNAME'], os.path.split(filepath)[1]))
                except Exception:
                    pass
        return scans

    def _findMostRecentProcScans(self, procname, count=1):
        """
        Find the most recent scan(s) that have the given procname.
        This returns an ordered list of the most recent scan(s),
        or 0s if the proper amount of scans can't be found.
        """
        scans = self._getScanProcedures()

        procScanNums = [0] * count

        calSeqScans = [(scan, file) for (scan, proc, file) in scans
                       if scan <= self.scanNum and proc == procname]

        if len(calSeqScans) == 0:
            return []

        for i in range(min(len(calSeqScans), count)):
            procScanNums[-i - 1] = calSeqScans[-i - 1]

        return procScanNums

class WBandCalibrator(CalSeqCalibrator):
    def getGains(self):
        """
        For this scan, calculate the gains from previous calseq scan.
        This has format {"1X": 0.0, "2X": 0.0, "1Y": 0.0, "2Y": 0.0}
        """
        calSeqScanNumInfo = self._findMostRecentProcScans("CALSEQ")

        if len(calSeqScanNumInfo) > 0:
            calSeqScanNum = calSeqScanNumInfo[0][0]
            cal = WBandCalibration()
            cal.makeCalScan(self.projPath, calSeqScanNum)
            return cal.calData[1]  # gains are in this spot
        return None


class ArgusCalibrator(CalSeqCalibrator):
    def getGains(self):
        """
        For this scan, calculate the gains from most recent VaneCal
        scan pair.
        This has format {"10X": 0.0, "11X": 0.0, "10Y": 0.0, "11Y": 0.0}
        """
        calSeqNums = self._findMostRecentProcScans("VANECAL", count=2)

        if all(calSeqNums):
            cal = ArgusCalibration(
                self.projPath, calSeqNums[0][1], calSeqNums[1][1]
            )
            return cal.getGain()
        return None


### Examples
# Calibrator(table, CalDiodeAttenuator, AvgPolCal, BeamSubtractCal)
# Calibrator(table, None, None, None).calibrate(Raw, X)
# Calibrator(table, None, InterPolAvg, None).calibrate(Raw, Avg)
# Calibrator(table, TotalPowerAtten, None, None).calibrate(X)
# Calibrator(table, KaSelector, TotalPowerAtten, None, None).calibrate(X)
# Calibrator(table, Generic, TotalPowerAtten, InterPolAvg, None).calibrate()
#



## How to get from GFM to this code?

# GFM: (Raw, XL)
# sel = GenericSelector(polOpt='XL')
# Calibrator(table, sel, None, None, None).calibrate()

# GFM: (TotalPower, XL)
# sel = GenericSelector(polOpt='XL')
# atten = TotalPowerAtten()
# Calibrator(table, sel, atten, None, None).calibrate()


# GFM: (TotalPower, Avg)
# sel = GenericSelector()
# atten = TotalPowerAtten()
# Calibrator(table, sel, atten, None, None).calibrate()

# GFM: (DualBeam, XL)
# sel = GenericSelector
# atten = TotalPowerAtten
# beam_sub = BeamSubtraction
# Calibrator(table, sel, atten, None, beam_sub).calibrate(polOpt='XL')


# GFM: (DualBeam, Avg)
# sel = GenericSelector
# atten = TotalPowerAtten
# pol_avg = PolAveraging
# beam_sub = BeamSubtraction
# Calibrator(table, sel, atten, pavg, beam_sub).calibrate(polOpt='Avg')

## OOF?
# GFM: (OofDualBeam, Avg)
# sel = OofSelector
# atten = OofTotalPowerAtten
# pol_avg = PolAveraging
# beam_sub = BeamSubtraction
# Calibrator(table, sel, atten, pavg, beam_sub).calibrate(polOpt='Avg')


# Ka?

# Argus?
