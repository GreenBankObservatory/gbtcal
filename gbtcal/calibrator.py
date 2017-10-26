"""Calibrator class hierarchy. A Calibrator is responsible for guiding
the calibration pipeline in a specific manner, usually for a receiver
or category of receivers"""

import logging
import os

from astropy.table import Column
from astropy.io import fits
import numpy

from constants import POLOPTS
from gbtcal.decode import getFitsForScan, getTcal, getRcvrCalTable
from table.querytable import QueryTable, copyTable
from gbtcal.attenuate import CalDiodeAttenuate, CalSeqAttenuate
from gbtcal.interpolops import InterPolAverage
from gbtcal.interbeamops import BeamSubtractionDBA
from WBandCalibration import WBandCalibration
from ArgusCalibration import ArgusCalibration

logger = logging.getLogger(__name__)

class Calibrator(object):
    """Outlines a three-step calibration pipeline. Stages are only
    executed if a class is provided to execute them"""

    def __init__(self, table,
                 performAttenuation=False,
                 performInterPolCal=False,
                 performInterBeamCal=False):
        self.logger = logging.getLogger("{}.{}".format(__name__,
                                                       self.__class__.__name__))
        self.table = table.copy()
        self.projPath = table.meta['PROJPATH']
        self.scanNum = table.meta['SCAN']
        self.performAttenuation = performAttenuation
        self.performInterPolCal = performInterPolCal
        self.performInterBeamCal = performInterBeamCal

        self.table.add_column(
            Column(name='FACTOR',
                   dtype=numpy.float64,
                   data=numpy.ones(len(self.table))
            )
        )

        @property
        def attenuator(self):
            raise NotImplementedError("All Calibrator subclasses must define "
                                      "an attenuator")
        @property
        def interPolCalibrator(self):
            raise NotImplementedError("All Calibrator subclasses must define "
                                      "an interPolCalibrator")
        @property
        def interBeamCalibrator(self):
            raise NotImplementedError("All Calibrator subclasses must define "
                                      "an interBeamCalibrator")

    def describe(self):
        """Describe the functionality of this Calibrator in its current configuration"""
        self.logger.info("My name is %s", self.__class__.__name__)
        self.logger.info("I will be calibrating this data:\n%s",
                    self.table)

        if self.attenuator:
            self.logger.info("I will perform attenuation using: %s",
                        self.attenuator.__class__.__name__)
        else:
            self.logger.info("I will perform NO attenuation")

        if self.interPolCalibrator:
            self.logger.info("I will perform inter-pol calibration using: %s",
                        self.interPolCalibrator.__class__.__name__)
        else:
            self.logger.info("I will perform NO inter-pol calibration")

        if self.interBeamCalibrator:
            self.logger.info("I will perform inter-beam calibration using: %s",
                        self.interBeamCalibrator.__class__.__name__)
        else:
            self.logger.info("I will perform NO inter-beam calibration")

    def getFeedForPol(self, pol):
        trackFeed = self.table.meta['TRCKBEAM']
        # First, find all of the feeds that contain the requested
        # polarization
        # TODO: This is not the correct location for this decision to be made!
        logger.debug("%s polarization has been requested")
        if pol == POLOPTS.AVG:
            logger.debug("Will process all feeds")
            feedsForPol = self.table.getUnique('FEED')
        else:
            logger.debug("Will process only feeds containing %s", pol)
            feedsForPol = self.table.query(POLARIZE=pol).getUnique('FEED')

        if trackFeed in feedsForPol:
            self.logger.debug("Selecting track feed")
            dataFeed = trackFeed
        else:
            self.logger.info("Track feed (%s) does not contain requested "
                        "polarization %s; arbitrarily selecting another "
                        "feed that does", trackFeed, pol)
            dataFeed = feedsForPol[0]
        # TODO: This is terrible; revert soon!
        pols = self.table.getUnique('POLARIZE')
        if pol not in pols and pol != POLOPTS.AVG:
            raise ValueError("Requested polarization {} does not exist "
                             "in the data table; has only {}"
                             .format(pol, list(pols)))

        self.logger.debug("Selected feed %s for requested polarization %s",
                     dataFeed, pol)
        return dataFeed

    def initCalTable(self):
        calTable = copyTable(self.table, ['FEED', 'POLARIZE', 'FACTOR'])
        calTable.add_column(Column(name='DATA',
                                   dtype=numpy.float64,
                                   shape=self.table['DATA'].shape[1]))
        self.logger.debug("Initialized calTable:\n%s", calTable)
        return calTable

    def initFeedTable(self, calTable):
        feedTable = QueryTable([numpy.unique(calTable['FEED'])])
        feedTable.add_column(Column(name='DATA',
                                    length=len(feedTable),
                                    dtype=numpy.float64,
                                    shape=calTable['DATA'].shape[1]))

        self.logger.debug("Initialized feedTable:\n%s", feedTable)
        return feedTable

    def findCalFactors(self):
        raise NotImplementedError("findCalFactors() must be implemented for "
                                  "all Calibrator subclasses!")

    def attenuate(self):
        # Populate FACTORS column with calibration factors (in place)
        self.logger.info("STEP: attenuate")
        self.findCalFactors()
        self.logger.debug("Populated cal factors")

        calTable = self.initCalTable()
        for row in self.table.getUnique(['FEED', 'POLARIZE']):
            feed = row['FEED']
            pol = row['POLARIZE']
            dataToAttenuate = self.table.query(FEED=feed, POLARIZE=pol)
            factor = dataToAttenuate['FACTOR'][0]
            power = self.attenuator.attenuate(dataToAttenuate)
            calTable.add_row({
                'FEED': feed,
                'POLARIZE': pol,
                'FACTOR': factor,
                'DATA': power
            })
        return calTable

    def dontAttenuate(self):
        self.logger.info("STEP: dontAttenuate")
        calOffTable = self.table.query(CAL=0)
        calTable = calOffTable['FEED', 'POLARIZE', 'FACTOR', 'DATA']
        return calTable

    def interPolCalibrate(self, feedTable, calTable):
        self.logger.info("STEP: interPolCalibrate")
        self.logger.debug("Performing inter-polarization calibration "
                     "using calibrator %s",
                     self.interPolCalibrator.__class__.__name__)
        for row in feedTable:
            feedMask = calTable['FEED'] == row['FEED']
            filteredCalTable = calTable[feedMask]
            row['DATA'] = self.interPolCalibrator.calibrate(filteredCalTable)

    def dontInterPolCalibrate(self, feedTable, calTable, polarization):
        self.logger.info("STEP: dontInterPolCalibrate")
        for row in feedTable:
            row['DATA'] = calTable.query(POLARIZE=polarization, FEED=row['FEED'])['DATA']

    def interBeamCalibrate(self, sigFeedData, refFeedData, polarization):
        self.logger.info("STEP: interBeamCalibrate")
        return self.interBeamCalibrator.calibrate(sigFeedData, refFeedData, polarization)

    def dontInterBeamCalibrate(self, feedTable, polarization):
        self.logger.debug("STEP: dontInterBeamCalibrate")
        feedMask = feedTable['FEED'] == self.getFeedForPol(polarization)
        feedData = feedTable[feedMask]['DATA'][0]
        return feedData

    def calibrate(self, polarization):
        if self.performAttenuation:
            # If we have an attenuator, then use it. This will
            # attenuate the data and populate the calData DATA column
            calTable = self.attenuate()
        else:
            # If not, we just remove all of our rows that have data
            # taking while the cal diode was on
            calTable = self.dontAttenuate()

        self.logger.debug("calTable after attenuation/\"real data\" selection:\n%s",
                          calTable)

        # So, we now have a calData table with a populated DATA column,
        # ready for the next stage
        # TODO: Don't init feedTable here; do same as calTable
        feedTable = self.initFeedTable(calTable)
        self.logger.debug("Initialized feed table:\n%s", feedTable)
        if self.performInterPolCal:
            # If we have an inter-pol calibrator, then use it. This will
            # calibrate the data between the two polarizations in the
            # calTable and store the results by feed in feedTable
            self.interPolCalibrate(feedTable, calTable)

        else:
            self.dontInterPolCalibrate(feedTable, calTable, polarization)

        self.logger.debug("Feed table after inter-pol calibration/pol selection:\n%s",
                          feedTable)

        if self.performInterBeamCal:
            self.logger.debug("Performing inter-beam calibration using "
                         "calibrator %s",
                         self.interBeamCalibrator.__class__.__name__)

            data = self.interBeamCalibrate(self.table, feedTable, polarization)
        else:
            data = self.dontInterBeamCalibrate(feedTable, polarization)

        self.logger.debug("Feed table after inter-beam calibration/beam selection:\n%s",
                          feedTable)
        self.logger.debug("Final calibrated data: [%f ... %f]", data[0], data[-1])
        return data


class TraditionalCalibrator(Calibrator):
    attenuator = CalDiodeAttenuate()
    interPolCalibrator = InterPolAverage()
    interBeamCalibrator = BeamSubtractionDBA()

    def findCalFactors(self):
        """Determine "factors" for data; use to populate FACTOR column"""

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


class KaCalibrator(TraditionalCalibrator):
    # Ka has two feeds and two polarizations, but only one polarization
    # exists in each feed

    def dontAttenuate(self):
        calTable = self.initCalTable()
        calOffTable = self.table.query(CAL=0)
        for feed in calOffTable.getUnique('FEED'):
            feedTable = calOffTable.query(FEED=feed)
            # TODO: Assert unique
            pol = feedTable['POLARIZE'][0]
            factor = feedTable['FACTOR'][0]
            feedSigData = feedTable.query(SIGREF=0)['DATA']
            feedRefData = feedTable.query(SIGREF=1)['DATA']
            power = feedSigData - feedRefData
            calTable.add_row({
                'FEED': feed,
                'POLARIZE': pol,
                'FACTOR': factor,
                'DATA': power
            })

        return calTable

    def dontInterPolCalibrate(self, feedTable, calTable, polarization):
        for row in feedTable:
            row['DATA'] = calTable.query(FEED=row['FEED'])['DATA']

    def getSigFeedTa(self, sigref, tcal):
        trackFeed = self.table.getTrackBeam()
        calOffTable = self.table.query(FEED=trackFeed, SIGREF=sigref, CAL=0)

        calOnTable = self.table.query(FEED=trackFeed, SIGREF=sigref, CAL=1)

        if len(calOffTable) != 1 or len(calOnTable) != 1:
            raise ValueError("There should be exactly one row each for "
                             "calOffTable (actual: {}) and "
                             "calOnTable (actual: {})"
                             .format(len(calOffTable),
                                     len(calOnTable)))

        if calOffTable['FACTOR'][0] != calOnTable['FACTOR'][0]:
            raise ValueError("tCal for reference beam should be identical "
                             "whether CAL is on or off")

        return self.attenuator.getAntennaTemperature(
            calOnData=calOnTable['DATA'][0],
            calOffData=calOffTable['DATA'][0],
            tCal=tcal
        )

    def attenuate(self):
        self.logger.info("STEP: attenuate")

        # Populate FACTORS column with calibration factors (in place)
        self.findCalFactors()
        self.logger.debug("Populated cal factors")

        calTable = self.initCalTable()


        sigFeed, refFeed = self.table.getSigAndRefFeeds()

        sigTcal = self.table.query(FEED=sigFeed)['FACTOR'][0]
        refTcal = self.table.query(FEED=refFeed)['FACTOR'][0]


        sigTa = self.getSigFeedTa(sigref=0, tcal=sigTcal)
        refTa = self.getSigFeedTa(sigref=1, tcal=refTcal)

        sigPol = self.table.query(FEED=sigFeed)['POLARIZE'][0]
        refPol = self.table.query(FEED=refFeed)['POLARIZE'][0]
        calTable.add_row({
            'FEED': sigFeed,
            'POLARIZE': sigPol,
            'FACTOR': sigTcal,
            'DATA': sigTa
        })
        calTable.add_row({
            'FEED': refFeed,
            'POLARIZE': refPol,
            'FACTOR': refTcal,
            'DATA': refTa
        })
        return calTable


class CalSeqCalibrator(Calibrator):
    attenuator = CalSeqAttenuate()
    interPolCalibrator = InterPolAverage()
    interBeamCalibrator = BeamSubtractionDBA()

    def findCalFactors(self):
        table = self.table
        # This is defined in the subclasses
        gains = self.getGains()
        if gains is None:
            # We didn't find the gains, so we want to keep FACTOR values 1.0
            self.logger.warning("Could not find gain values. Setting all gains to 1.0")
            return

        for row in table:
            index = str(row['FEED']) + row['POLARIZE']
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
