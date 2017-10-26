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

        if self.performAttenuation:
            self.logger.info("I will perform attenuation using: %s",
                        self.attenuator.__class__.__name__)
        else:
            self.logger.info("I will perform NO attenuation")

        if self.performInterPolCal:
            self.logger.info("I will perform inter-pol calibration using: %s",
                        self.interPolCalibrator.__class__.__name__)
        else:
            self.logger.info("I will perform NO inter-pol calibration")

        if self.performInterBeamCal:
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
        # Create the blank cal table by using self.table as a template
        # and keeping only these three columns
        calTable = copyTable(self.table, ['FEED', 'POLARIZE', 'FACTOR'])
        # Then add the data column, but don't populate it yet
        calTable.add_column(Column(name='DATA',
                                   dtype=numpy.float64,
                                   shape=self.table['DATA'].shape[1]))
        # Set the sig and ref feeds so they can be extracted later
        sigFeed, refFeed = self.table.getSigAndRefFeeds()
        calTable.meta['SIGFEED'] = sigFeed
        calTable.meta['REFFEED'] = refFeed

        self.logger.info("Initialized calTable:\n%s", calTable)
        return calTable

    def initPolTable(self, calTable):
        # Create new table with rows for each unique polarization in the
        # calTable
        polTable = QueryTable([calTable.getUnique('POLARIZE')])
        # Then add the data column, but don't populate it yet
        polTable.add_column(Column(name='DATA',
                                    length=len(polTable),
                                    dtype=numpy.float64,
                                    shape=calTable['DATA'].shape[1]))

        self.logger.info("Initialized polTable:\n%s", polTable)
        return polTable

    def findCalFactors(self):
        raise NotImplementedError("findCalFactors() must be implemented for "
                                  "all Calibrator subclasses!")

    def attenuate(self):
        self.logger.info("STEP: attenuate")
        # Populate FACTORS column with calibration factors (in place)
        self.findCalFactors()
        self.logger.debug("Populated cal factors")

        calTable = self.initCalTable()
        for feed, pol in self.table.getUnique(['FEED', 'POLARIZE']):
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

    def selectNonCalData(self):
        self.logger.info("STEP: selectNonCalData")
        calOffTable = self.table.query(CAL=0)
        calTable = self.initCalTable()
        for feed, pol in self.table.getUnique(['FEED', 'POLARIZE']):
            calTable.add_row({
                'FEED': feed,
                'POLARIZE': pol,
                'FACTOR': 1.0,  # We didn't attenuate, so set factor to 1
                'DATA': calOffTable.query(FEED=feed, POLARIZE=pol)['DATA'][0]
             })

        return calTable

    def interPolCalibrate(self, polTable):
        self.logger.info("STEP: interPolCalibrate")
        return self.interPolCalibrator.calibrate(polTable)

    def selectPol(self, polTable, polarization):
        self.logger.info("STEP: selectPol")
        return polTable.query(POLARIZE=polarization)['DATA'][0]

    def interBeamCalibrate(self, calTable):
        self.logger.info("STEP: interBeamCalibrate")
        polTable = self.initPolTable(calTable)
        for row in polTable:
            polMask = calTable['POLARIZE'] == row['POLARIZE']
            calTableForPol = calTable[polMask]
            row['DATA'] = self.interBeamCalibrator.calibrate(calTableForPol)

        return polTable

    def selectBeam(self, calTable, feed):

        logger.info("Creating polTable from sig feed %d in calTable", feed)
        polTable = self.initPolTable(calTable)
        filteredCalTable = calTable.query(FEED=feed)
        for row in polTable:
            # Get the data from the row of the filtered calTable with the current
            # row's polarization
            polMask = filteredCalTable['POLARIZE'] == row['POLARIZE']
            row['DATA'] = filteredCalTable[polMask]['DATA'][0]

        return polTable

    def calibrate(self, polarization):
        if self.performAttenuation:
            # If we have an attenuator, then use it. This will
            # attenuate the data and populate the calData DATA column
            calTable = self.attenuate()
        else:
            # If not, we just remove all of our rows that have data
            # taking while the cal diode was on
            calTable = self.selectNonCalData()

        self.logger.info("calTable after attenuation/\"real data\" selection:\n%s",
                          calTable)
        if self.performInterBeamCal:
            self.logger.info("Performing inter-beam calibration using "
                             "calibrator %s",
                             self.interBeamCalibrator.__class__.__name__)
            polTable = self.interBeamCalibrate(calTable)
        else:
            polTable = self.selectBeam(calTable, calTable.meta['SIGFEED'])

        self.logger.info("pol table after inter-beam calibration/beam selection:\n%s",
                          polTable)

        # So, we now have a calData table with a populated DATA column,
        # ready for the next stage
        if self.performInterPolCal:
            # If we have an inter-pol calibrator, then use it. This will
            # calibrate the data between the two polarizations in the
            # calTable and store the results by feed in polTable
            data = self.interPolCalibrate(polTable)

        else:
            data = self.selectPol(polTable, polarization)

        self.logger.info("Final calibrated data: [%f ... %f]", data[0], data[-1])
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

    def selectNonCalData(self):
        calTable = self.initCalTable()
        calOffTable = self.table.query(CAL=0)
        for feed in calOffTable.getUnique('FEED'):
            polTable = calOffTable.query(FEED=feed)
            # TODO: Assert unique
            pol = polTable['POLARIZE'][0]
            factor = polTable['FACTOR'][0]
            feedSigData = polTable.query(SIGREF=0)['DATA']
            feedRefData = polTable.query(SIGREF=1)['DATA']
            power = feedSigData - feedRefData
            calTable.add_row({
                'FEED': feed,
                'POLARIZE': pol,
                'FACTOR': factor,
                'DATA': power
            })

        return calTable

    def selectBeam(self, calTable, feed):
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
