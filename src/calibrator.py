import os
import numpy

from astropy.io import fits
from astropy.table import Column

from dcr_decode_astropy import getFitsForScan, getTcal, getRcvrCalTable
from CalibrationResults import CalibrationResults
from ArgusCalibration import ArgusCalibration


class Calibrator(object):
    def __init__(self, receiverInfoTable, ifDcrDataTable):
        self._receiverInfoTable = receiverInfoTable
        self._ifDcrDataTable = ifDcrDataTable
        self.projPath = ifDcrDataTable.meta['PROJPATH']
        self.scanNum = ifDcrDataTable.meta['SCAN']

    @property
    def receiverInfoTable(self):
        return self._receiverInfoTable

    @property
    def ifDcrDataTable(self):
        return self._ifDcrDataTable

    def findCalFactors(self, data):
        raise NotImplementedError("findCalFactors() must be implemented for "
                                  "all Calibrator subclasses!")

    def doMath(self, data, doGain, polOption, refBeam):
        """Set up the calculations for all calibration types."""
        # handle single pols, or averages
        allPols = numpy.unique(data['POLARIZE'])
        allPols = numpy.char.rstrip(allPols).tolist()

        if polOption == 'Both':
            pols = allPols
        else:
            pols = [polOption]

        trackBeam = data.meta['TRCKBEAM']

        print("TRACK BEAM::: ", trackBeam)

        feeds = numpy.unique(data['FEED'])

        if trackBeam not in feeds:
            # TODO: RAISE ERROR
            # TrackBeam must be wrong?
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
                freq = self.getFreqForData(data, feed, pol)
                if doGain:
                    powerPol = self.calibrateTotalPower(data, feed, pol, freq)
                else:
                    powerPol = self.getRawPower(data, feed, pol, freq)
                polPowers.append(powerPol)
            totals[feed] = sum(polPowers) / float(len(pols))

        # If refBeam is True, then Dual Beam
        if refBeam:
            if numpy.unique(data['FEED']) != 2:
                raise ValueError("Data table must contain exactly two "
                                 "unique feeds to perform "
                                 "dual beam calibration")

            return self.calibrateDualBeam(totals, trackBeam, feeds)
        else:
            # total power
            return totals[feeds[0]]

    def calibrateDualBeam(self, feedTotalPowers, trackBeam, feeds):
        """Here we're just finding the difference between the two beams"""
        # TODO: REMOVE FROM CLASS?
        assert len(feeds) == 2
        if trackBeam == feeds[0]:
            sig, ref = feeds
        else:
            ref, sig = feeds

        return feedTotalPowers[sig] - feedTotalPowers[ref]

    def getRawPower(self, data, feed, pol, freq):
        """Simply get the raw power, for the right phase"""
        print("getRawPower", feed, pol, freq)
        phases = numpy.unique(data['SIGREF', 'CAL'])
        phase = (0, 0) if len(phases) > 1 else phases[0]

        sigref, cal = phase
        mask = (
            (data['FEED'] == feed) &
            (data['SIGREF'] == sigref) &
            (data['CAL'] == cal) &
            (data['CENTER_SKY'] == freq) &
            (numpy.char.rstrip(data['POLARIZE']) == pol)
        )

        raw = data[mask]
        assert len(raw) == 1, \
            "There should only ever be one row of data for getRawPower"
        return raw['DATA']

    def getFreqForData(self, data, feed, pol):
        """Get the first data's frequency that has the given feed and polarization"""
        # TODO: REMOVE FROM CLASS?

        mask = (
            (data['FEED'] == feed) &
            (numpy.char.rstrip(data['POLARIZE']) == pol)
        )
        if len(numpy.unique(data[mask]['CENTER_SKY'])) != 1:
            raise ValueError("Should be only one CENTER_SKY "
                             "for a given FEED and POLARIZE")

        return data[mask]['CENTER_SKY'][0]

    def calibrate(self, polOption='Both', doGain=True, refBeam=False):
        newTable = self.ifDcrDataTable.copy()

        newTable.add_column(
            Column(name='FACTOR',
                   dtype=numpy.float64,
                   data=numpy.ones(len(newTable))))
        if doGain:
            self.findCalFactors(newTable)

        return self.doMath(newTable, doGain, polOption, refBeam)[0]


class TraditionalCalibrator(Calibrator):
    def findCalFactors(self, data):
        print("Looking at tCals and stuff")

        receiver = data['RECEIVER'][0]

        fitsForScan = getFitsForScan(self.projPath, self.scanNum)
        rcvrCalHduList = fitsForScan[receiver]
        rcvrCalTable = getRcvrCalTable(rcvrCalHduList)

        # TODO: Double check this assumption
        uniqueRows = numpy.unique(data['FEED', 'POLARIZE',
                                       'CENTER_SKY', 'BANDWDTH',
                                       'HIGH_CAL'])
        for feed, pol, centerSkyFreq, bandwidth, highCal in uniqueRows:
            mask = ((data['FEED'] == feed) &
                    (data['POLARIZE'] == pol) &
                    (data['CENTER_SKY'] == centerSkyFreq) &
                    (data['BANDWDTH'] == bandwidth) &
                    (data['HIGH_CAL'] == highCal))

            maskedData = data[mask]

            if len(numpy.unique(maskedData['RECEPTOR'])) != 1:
                raise ValueError("The rows in the receiver calibration file "
                                 "must all be unique for all "
                                 "feed/polarization/frequency groupings.")

            receptor = maskedData['RECEPTOR'][0]

            tCal = getTcal(rcvrCalTable, feed, receptor, pol,
                           highCal, centerSkyFreq, bandwidth)
            for row in data[mask]:
                # TODO: Cleaner way of doing this?
                data[row['INDEX']]['FACTOR'] = tCal

    def getAntennaTemperature(self, calOnData, calOffData, tCal):
        countsPerKelvin = (numpy.sum((calOnData - calOffData) / tCal) /
                           len(calOnData))
        Ta = 0.5 * (calOnData + calOffData) / countsPerKelvin - 0.5 * tCal
        return Ta

    def calibrateTotalPower(self, data, feed, pol, freq, refPhase=False):
        # NOTE: This is AGNOSTIC to SIGREF. That is, it cares only about CAL

        mask = (
            (data['FEED'] == feed) &
            (numpy.char.rstrip(data['POLARIZE']) == pol) &
            (data['CENTER_SKY'] == freq)
            # TODO: Not sure if this should be here or not...
            # (data['SIGREF'] == 0)
        )

        dataToCalibrate = data[mask]

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
            raise ValueError("TCAL of 'on' and 'off' data must be identical")

        # TODO: This is probably a bug in the decode code...
        # This is an array of a single array, so we extract the inner array
        onData = onRow['DATA'][0]
        offData = offRow['DATA'][0]
        # Doesn't matter which row we grab this from; they are identical
        tCal = onRow['FACTOR']
        temp = self.getAntennaTemperature(onData, offData, tCal)
        # Need to put this BACK into an array where the only element is
        # the actual array
        # TODO: This is sooooo dumb, plz fix
        return numpy.array([temp])


class KaCalibrator(TraditionalCalibrator):

    """
    The Ka receiver (Rcvr26_40) only has one polarization per feed:
    feed 1: YR; feed 2: XL
    Also, instead of DualBeam polarization, we use BeamSwitchedTBOnly
    """

    def __init__(self, receiverInfoTable, ifDcrDataTable):
        super(KaCalibrator, self).__init__(receiverInfoTable,
                                           ifDcrDataTable)
        self.kaBeamMap = {1: 'R', 2: 'L'}
        self.kaPolMap = {'R': 1, 'L': 2}

    def calibrateTotalPower(self, data, feed, pol, freq):
        "Calibrate the total power, but only for valid polarization"
        # pol = self.kaBeamMap[feed]
        feed = self.kaPolMap[pol]
        return super(KaCalibrator, self).calibrateTotalPower(data,
                                                             feed,
                                                             pol,
                                                             freq)

    def getFreqForData(self, data, feed, pol):
        # pol = self.kaBeamMap[feed]
        feed = self.kaPolMap[pol]
        return super(KaCalibrator, self).getFreqForData(data, feed, pol)


class CalSeqCalibrator(Calibrator):
    def findCalFactors(self, data):
        print("Finding cal factors for Cal Seq situation")
        # This is defined in the subclasses
        gains = self.getGains()
        if gains is None:
            # We didn't find the gains, so we want to keep FACTOR values 1.0
            print("Could not find gain values. Setting all gains to 1.0")
            return
        print("GAINS IS: ", gains)
        for row in data:
            index = str(row['FEED']) + row['POLARIZE']
            data[row['INDEX']]['FACTOR'] = gains[index]

    def calibrateTotalPower(self, data, feed, pol, freq):
        """Total power for External Cals is just the off with a gain."""
        offMask = (
            (data['FEED'] == feed) &
            (numpy.char.rstrip(data['POLARIZE']) == pol) &
            (data['CENTER_SKY'] == freq) &
            (data['CAL'] == 0)
        )

        offRow = data[offMask]

        if len(offRow) != 1:
            raise ValueError("Must be exactly one row for 'off' data")

        # TODO: This is probably a bug in the decode code...
        # This is an array of a single array, so we extract the inner array
        offData = offRow['DATA'][0]
        # Doesn't matter which row we grab this from; they are identical
        gain = offRow['FACTOR']
        # Need to put this BACK into an array where the only element is
        # the actual array
        # TODO: This is sooooo dumb, plz fix
        calData = gain * (offData - numpy.median(offData))
        return numpy.array([calData])

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
                    scans.append((scan, h['PROCNAME'], os.path.split(filepath)[1]))
                except Exception:
                    print "Could not find GO file, skipping #{}.".format(scan)
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

        for i in range(min(len(calSeqScans), count)):
            procScanNums[-i - 1] = calSeqScans[-i - 1]

        return procScanNums


class WBandCalibrator(CalSeqCalibrator):
    def getGains(self):
        """
        For this scan, calculate the gains from previous calseq scan.
        This has format {"1X": 0.0, "2X": 0.0, "1Y": 0.0, "2Y": 0.0}
        """
        calSeqScanNum = self._findMostRecentProcScans("CALSEQ")[0][0]

        if calSeqScanNum:
            cal = CalibrationResults()
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


class InvalidCalibrator(Calibrator):
    pass
