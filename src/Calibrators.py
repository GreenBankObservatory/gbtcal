import os

import numpy
from astropy.io import fits
from astropy.table import Column

from dcr_decode import getFitsForScan, getTcal, getRcvrCalTable

from WBandCalibration import WBandCalibration
from ArgusCalibration import ArgusCalibration
from constants import POLS, POLOPTS
from util import wprint


class Calibrator(object):
    def __init__(self, ifDcrDataTable):
        self._ifDcrDataTable = ifDcrDataTable
        self.projPath = ifDcrDataTable.meta['PROJPATH']
        self.scanNum = ifDcrDataTable.meta['SCAN']

    @property
    def ifDcrDataTable(self):
        return self._ifDcrDataTable

    def findCalFactors(self, data):
        raise NotImplementedError("findCalFactors() must be implemented for "
                                  "all Calibrator subclasses!")

    def doMath(self, table, doGain, polOption, refBeam):
        """Set up the calculations for all calibration types."""
        # handle single pols, or averages
        allPols = numpy.unique(table['POLARIZE'])
        allPols = allPols.tolist()

        validPols = [POLS.isValid(pol) for pol in allPols]
        if not all(validPols):
            raise ValueError("Invalid/Unsupported polarizations detected. "
                             "{} are not in {}"
                             .format([pol for pol in allPols
                                      if not POLS.isValid(pol)],
                                     POLS.all()))

        if polOption == POLOPTS.AVG:
            pols = allPols
        else:
            pols = [polOption]

        trackBeam = table.meta['TRCKBEAM']

        feeds = numpy.unique(table['FEED'])

        if trackBeam not in feeds:
            # WTF!  How to know which feed to use for raw & tp?
            # we've experimented and shown that there's no happy ending here.
            # so just bail.
            raise ValueError("The track beam is not one of the feeds in the "
                             "table. Can't do any useful data processing.")

        if not refBeam:
            # If only calibrating one beam, don't worry about the other beam.
            feeds = [trackBeam]

        # collect total powers from each feed
        totals = {}
        for feed in feeds:
            # make this general for both a single pol, and averaging
            polPowers = []
            for pol in pols:
                freq = self.getFreqForData(table, feed, pol)
                if doGain:
                    # TODO: This logic seems naughty... Calibrator shouldn't
                    # have any specific knowledge about its children. Though
                    # perhaps this is generic enough that it could be made
                    # top level? That would work...
                    powerPol = self.calibrateTotalPower(table, feed, pol, freq)
                else:
                    powerPol = self.getRawPower(table, feed, pol, freq)
                polPowers.append(powerPol)

            totals[feed] = numpy.sum(polPowers, axis=0) / len(pols)

        # Put the calibrated data in the table metadata
        # TODO: This seems somewhat naughty still...
        table.meta['calibratedData'] = totals

        # If refBeam is True, then Dual Beam
        if refBeam:
            if len(numpy.unique(table['FEED'])) != 2:
                raise ValueError("Data table must contain exactly two "
                                 "unique feeds to perform "
                                 "dual beam calibration")
            # import ipdb; ipdb.set_trace()
            return self.calibrateDualBeam(table)
        else:
            # total power
            # TODO: Why is this feeds[0]? Shouldn't it be TRCKBEAM?
            return totals[feeds[0]]

    def determineTrackFeed(self, table):
        feeds = table.getUnique('FEED')
        trackBeam = table.meta['TRCKBEAM']
        if len(feeds) < 2:
            raise ValueError("Must have at least two feeds to determine "
                             "the tracking/reference feeds")
        elif len(feeds > 2):
            wprint("More than two feeds provided; reference feed will be "
                   "ambiguous")

        if trackBeam == feeds[0]:
            sig = feeds[0]
            ref = feeds[1]
        else:
            sig = feeds[1]
            ref = feeds[0]
        return sig, ref

    def calibrateDualBeam(self, table):
        """Here we're just finding the difference between the two beams"""
        # TODO: REMOVE FROM CLASS?
        sigFeed, refFeed = self.determineTrackFeed(table)
        calibratedData = table.meta['calibratedData']
        return calibratedData[sigFeed] - calibratedData[refFeed]

    def getRawPower(self, table, feed, pol, freq):
        """Raw power is be simply the data straight from the table"""
        sig = self.getSignalRawPower(table, feed, pol, freq)
        ref = self.getRefRawPower(table, feed, pol, freq)
        return (sig - ref) if ref is not None else sig

    def getSignalRawPower(self, table, feed, pol, freq):
        """Simply get the raw power, for the right phase"""
        phases = table.getUnique(['SIGREF', 'CAL'])

        # Default phase to SIGREF=0, CAL=0
        # TODO: Why are we doing this?
        phase = (0, 0) if len(phases) > 1 else phases[0]
        sigref, cal = phase

        mask = (
            (table['FEED'] == feed) &
            (table['SIGREF'] == sigref) &
            (table['CAL'] == cal) &
            (table['CENTER_SKY'] == freq) &
            (table['POLARIZE'] == pol)
        )

        rawData = table[mask]['DATA']
        if len(rawData) != 1:
            raise ValueError("There should be exactly one row of data "
                             "for getSignalRawPower; got {}"
                             .format(len(rawData)))
        return rawData

    def getRefRawPower(self, table, feed, pol, freq):
        """Simply get the raw power for the reference phase"""
        phases = table.getUnique(['SIGREF', 'CAL'])
        # TBD: need to convert this or the next check fails
        phs = [(p[0], p[1]) for p in list(phases)]
        refPhase = (1, 0)
        if refPhase not in phs:
            # bail if we simply don't have that phase
            return None

        sigref, cal = refPhase
        mask = (
            (table['FEED'] == feed) &
            (table['SIGREF'] == sigref) &
            (table['CAL'] == cal) &
            (table['CENTER_SKY'] == freq) &
            (table['POLARIZE'] == pol)
        )

        rawData = table[mask]['DATA']
        if len(rawData) != 1:
            raise ValueError("There should be exactly one row of data "
                             "for getSignalRawPower; got {}"
                             .format(len(rawData)))
        return rawData

    def getFreqForData(self, table, feed, pol):
        """
        Get the first data's frequency that has the given feed and polarization
        """
        # TODO: REMOVE FROM CLASS?

        if not POLS.isValid(pol):
            raise ValueError("Given polarization '{}' is invalid. Valid "
                             "polarizations are: {}"
                             .format(pol, POLS.all()))

        mask = (
            (table['FEED'] == feed) &
            (table['POLARIZE'] == pol)
        )

        feedTable = table[mask]
        numUniqueFreqs = len(feedTable.getUnique(['CENTER_SKY']))

        if numUniqueFreqs != 1:
            raise ValueError("Should be exactly one CENTER_SKY "
                             "for a given FEED and POLARIZE; "
                             "got {} unique freq values."
                             .format(numUniqueFreqs))

        return feedTable['CENTER_SKY'][0]

    def calibrate(self, polOption, doGain, refBeam):
        newTable = self.ifDcrDataTable.copy()

        newTable.add_column(
            Column(name='FACTOR',
                   dtype=numpy.float64,
                   data=numpy.ones(len(newTable))))
        if doGain:
            self.findCalFactors(newTable)

        return self.doMath(newTable, doGain, polOption, refBeam)


class TraditionalCalibrator(Calibrator):
    def findCalFactors(self, table):
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
            for row in table[mask]:
                # TODO: Cleaner way of doing this?
                table[row['INDEX']]['FACTOR'] = tCal

    def getAntennaTemperature(self, calOnData, calOffData, tCal):
        countsPerKelvin = (numpy.sum((calOnData - calOffData) / tCal) /
                           len(calOnData))
        Ta = 0.5 * (calOnData + calOffData) / countsPerKelvin - 0.5 * tCal
        return Ta

    def calibrateTotalPower(self, table, feed, pol, freq, refPhase=False):
        # NOTE: This is AGNOSTIC to SIGREF. That is, it cares only about CAL

        mask = (
            (table['FEED'] == feed) &
            (table['POLARIZE'] == pol) &
            (table['CENTER_SKY'] == freq)
            # TODO: Not sure if this should be here or not...
            # (table['SIGREF'] == 0)
        )

        dataToCalibrate = table[mask]

        ref = 1 if refPhase else 0

        onMask = (
            (dataToCalibrate['CAL'] == 1) &
            (dataToCalibrate['SIGREF'] == ref)
        )
        offMask = (
            (dataToCalibrate['CAL'] == 0) &
            (dataToCalibrate['SIGREF'] == ref)
        )

        onRow = dataToCalibrate[onMask]
        offRow = dataToCalibrate[offMask]

        if len(onRow) != 1 or len(offRow) != 1:
            raise ValueError("Must be exactly one row each for "
                             "'on' and 'off' data")

        if onRow['FACTOR'] != offRow['FACTOR']:
            raise ValueError("FACTOR of 'on' and 'off' data must be identical")

        onData = onRow['DATA'][0]
        offData = offRow['DATA'][0]
        # Doesn't matter which row we grab this from; they are identical
        tCal = onRow['FACTOR'][0]
        temp = self.getAntennaTemperature(onData, offData, tCal)
        return temp


class KaCalibrator(TraditionalCalibrator):

    """
    The Ka receiver (Rcvr26_40) only has one polarization per feed:
    feed 1: YR; feed 2: XL
    Also, instead of DualBeam polarization, we use BeamSwitchedTBOnly
    """

    def __init__(self, ifDcrDataTable):
        super(KaCalibrator, self).__init__(ifDcrDataTable)
        # TBD: should this be in the master receiver table?
        self.kaBeamMap = {1: 'R', 2: 'L'}
        self.kaPolMap = {'R': 1, 'L': 2}

    def calibrateTotalPower(self, table, feed, pol, freq):
        "Calibrate the total power, but only for valid polarization"
        feed = self.kaPolMap[pol]
        return super(KaCalibrator, self).calibrateTotalPower(table,
                                                             feed,
                                                             pol,
                                                             freq)

    def getRawPower(self, table, feed, pol, freq):
        "Calibrate the raw power, but only for valid polarization"
        feed = self.kaPolMap[pol]
        return super(KaCalibrator, self).getRawPower(table,
                                                     feed,
                                                     pol,
                                                     freq)

    def getFreqForData(self, table, feed, pol):
        "Get the frequency, but only for valid polarization"
        feed = self.kaPolMap[pol]
        return super(KaCalibrator, self).getFreqForData(table, feed, pol)



    def calibrateBeamSwitchedTBOnly(self, table):
        """Given a data table, calibrate based on the indicated track beam
        and return the result."""

        # NOTE: There is an important distinction here between the
        # signal/reference _feeds_ and the SIGREF column. The signal feed
        # can have its SIGREF column indicate 'reference', and vice versa.
        # So, the variable names here are very verbose to ensure accuracy

        sigFeed, refFeed = self.determineTrackFeed(table)

        # get the total power of the tracking beam's signal phases
        # TODO: This map should not live here!
        kaPolMap = {1: 'R', 2: 'L'}

        # Polarization for the signal feed
        sigPol = kaPolMap[sigFeed]
        # Frequency for the signal feed
        sigFreq = self.getFreqForData(table, sigFeed, sigPol)
        # Create a table containing for the signal feed
        sigFeedMask = (
            (table['FEED'] == sigFeed) &
            (table['POLARIZE'] == sigPol) &
            (table['CENTER_SKY'] == sigFreq)
        )
        sigFeedTable = table[sigFeedMask]

        # From the data in the signal feed table, create a table
        # containing only the rows where SIGREF indicated SIG
        sigFeedSigMask = (sigFeedTable['SIGREF'] == 0)
        sigFeedSigTable = sigFeedTable[sigFeedSigMask]

        # Now, select the rows where the cal diode was on...
        sigCalOnMask = (sigFeedSigTable['CAL'] == 1)
        sigCalOn = sigFeedSigTable[sigCalOnMask]

        # ...and the rows where it was off
        sigCalOffMask = (sigFeedSigTable['CAL'] == 0)
        sigCalOff = sigFeedSigTable[sigCalOffMask]

        if sigCalOn['FACTOR'][0] != sigCalOff['FACTOR'][0]:
            raise ValueError("tCal for signal beam should be identical "
                             "whether CAL is on or off")

        if len(sigFeedTable.getUnique('FACTOR')) != 1:
            raise ValueError("There must be only one tCal value for a given "
                             "feed")
        # Get the tCal for the signal beam
        sigTcal = sigFeedTable['FACTOR'][0]
        sigTa = self.getAntennaTemperature(sigCalOn['DATA'][0],
                                           sigCalOff['DATA'][0],
                                           sigTcal)

        # From the data in the signal feed table, create a table
        # containing only the rows where SIGREF indicated REF
        sigFeedRefMask = (sigFeedTable['SIGREF'] == 1)
        sigFeedRefTable = sigFeedTable[sigFeedRefMask]

        sigFeedRefCalOnMask = (sigFeedRefTable['CAL'] == 1)
        sigFeedRefCalOnTable = sigFeedRefTable[sigFeedRefCalOnMask]

        sigFeedRefCalOffMask = (sigFeedRefTable['CAL'] == 0)
        sigFeedRefCalOffTable = sigFeedRefTable[sigFeedRefCalOffMask]
        if len(sigFeedRefCalOffTable) != 1 or len(sigFeedRefCalOnTable) != 1:
            raise ValueError("There should be exactly one row each for "
                             "sigFeedRefCalOnTable (actual: {}) and "
                             "sigFeedRefCalOffTable (actual: {})"
                             .format(len(sigFeedRefCalOnTable),
                                     len(sigFeedRefCalOffTable)))

        if sigFeedRefCalOnTable['FACTOR'][0] != sigFeedRefCalOffTable['FACTOR'][0]:
            raise ValueError("tCal for reference beam should be identical "
                             "whether CAL is on or off")

        # Pick any of the reference feed rows to get the reference beam TCal
        refTcal = table[table['FEED'] == refFeed]['FACTOR'][0]
        refTa = self.getAntennaTemperature(sigFeedRefCalOnTable['DATA'][0],
                                           sigFeedRefCalOffTable['DATA'][0],
                                           refTcal)

        return sigTa - refTa

    def calibrateDualBeam(self, table):
        return self.calibrateBeamSwitchedTBOnly(table)


class CalSeqCalibrator(Calibrator):
    def findCalFactors(self, table):
        # This is defined in the subclasses
        gains = self.getGains()
        if gains is None:
            # We didn't find the gains, so we want to keep FACTOR values 1.0
            wprint("Could not find gain values. Setting all gains to 1.0")
            return

        for row in table:
            index = str(row['FEED']) + row['POLARIZE']
            table[row['INDEX']]['FACTOR'] = gains[index]

    def calibrateTotalPower(self, table, feed, pol, freq):
        """Total power for External Cals is just the off with a gain."""
        offMask = (
            (table['FEED'] == feed) &
            (table['POLARIZE'] == pol) &
            (table['CENTER_SKY'] == freq) &
            (table['CAL'] == 0)
        )

        offTable = table[offMask]

        if len(offTable) != 1:
            raise ValueError("Must be exactly one row for 'off' data")

        # This is an array of a single array, so we extract the inner array
        offData = offTable['DATA'][0]
        # Doesn't matter which row we grab this from; they are identical
        gain = offTable['FACTOR']
        # Need to put this BACK into an array where the only element is
        # the actual array
        calData = gain * (offData - numpy.median(offData))
        return calData

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
