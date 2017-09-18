import os
import numpy

from astropy.io import fits
from astropy.table import Column, Table, hstack, vstack

from dcr_table import stripTable
from dcr_decode_astropy import getFitsForScan, getTcal, getRcvrCalTable
from CalibrationResults import CalibrationResults


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

    def doMath(self, dataTable, polOption, refBeam):
        # This is the same for all "Cal Seq" calibrators -- right now
        # just W band and Argus
        print("Doing math for Cal Seq calibration")

        # handle single pols, or averages
        allPols = numpy.unique(dataTable['POLARIZE'])
        allPols = numpy.char.rstrip(allPols).tolist()

        if polOption == 'Both':
            pols = allPols
        else:
            pols = [polOption]

        trackBeam = dataTable.meta['TRCKBEAM']

        print("TRACK BEAM::: ", trackBeam)

        feeds = numpy.unique(dataTable['FEED'])

        if trackBeam not in feeds:
            # TrackBeam must be wrong?
            # WTF!  How to know which feed to use for raw & tp?
            # we've experimented and shown that there's no happy ending here.
            # so just bail.
            return None

        if not refBeam:
            # If only calibrating one beam, don't worry about the other beam.
            feeds = [trackBeam]

        # collect total powers from each feed
        totals = {}
        for feed in feeds:
            # make this general for both a single pol, and averaging
            polPowers = []
            for pol in pols:
                freq = getFreqForData(dataTable, feed, pol)
                totalPowerPol = self.calibrateTotalPower(dataTable, feed, pol, freq)
                polPowers.append(totalPowerPol)
            totals[feed] = sum(polPowers) / float(len(pols))

        # If refBeam is True, then Dual Beam
        if refBeam:
            if numpy.unique(dataTable['FEED']) != 2:
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

    def getFreqForData(self, data, feed, pol):
        """Get the first data's frequency that has the given feed and polarization"""
        # TODO: REMOVE FROM CLASS?

        mask = (
            (data['FEED'] == feed) &
            (np.char.rstrip(data['POLARIZE']) == pol)
        )

        if len(np.unique(data[mask]['CENTER_SKY'])) != 1:
            raise ValueError("Should be only one CENTER_SKY "
                             "for a given FEED and POLARIZE")

        return data[mask]['CENTER_SKY'][0]

    def calibrate(self, polOption='Both', doGain=True, refBeam=False):
        newTable = self.ifDcrDataTable.copy()
        # TODO: Shouldn't have to do this; should be done already
        stripTable(newTable)

        # TODO: Should this be done here? Opens the possibility of
        # some error silently preventing the replacement
        # of this column with the _real_ factors...
        newTable.add_column(
            Column(name='FACTOR',
                   dtype=numpy.float64,
                   data=numpy.ones(len(newTable))))
        if doGain:
            self.findCalFactors(newTable)

        return self.doMath(newTable, polOption, refBeam)


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
        countsPerKelvin = (np.sum((calOnData - calOffData) / tCal) /
                           len(calOnData))
        Ta = 0.5 * (calOnData + calOffData) / countsPerKelvin - 0.5 * tCal
        return Ta

    def calibrateTotalPower(dataTable, feed, pol, freq):
        # NOTE: This is AGNOSTIC to SIGREF. That is, it cares only about CAL

        mask = (
            (data['FEED'] == feed) &
            (np.char.rstrip(data['POLARIZE']) == pol) &
            (data['CENTER_SKY'] == freq)
            # TODO: Not sure if this should be here or not...
            # (data['SIGREF'] == 0)
        )

        dataToCalibrate = data[mask]
        onMask = dataToCalibrate['CAL'] == 1
        offMask = dataToCalibrate['CAL'] == 0

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
        print("ON:", onData[0])
        print("OFF:", offData[0])
        print("TCAL:", tCal)
        # print(dataToCalibrate)
        # import ipdb; ipdb.set_trace()
        temp = self.getAntennaTemperature(onData, offData, tCal)
        print("TEMP: ", temp)
        # Need to put this BACK into an array where the only element is
        # the actual array
        # TODO: This is sooooo dumb, plz fix
        return np.array([temp])


class CalSeqCalibrator(Calibrator):
    def findCalFactors(self, data):
        print("Finding cal factors for W band using Cal Seq and stuff")
        # This is defined in the subclasses
        gains = self.getGains()
        for row in data:
            index = str(row['FEED']) + row['POLARIZE']
            row['FACTOR'] = gains[index]
        return row

    def calibrateTotalPower(dataTable, feed, pol, freq):
        """Total power for External Cals is just the off with a gain."""

        mask = (
            (data['FEED'] == feed) &
            (np.char.rstrip(data['POLARIZE']) == pol) &
            (data['CENTER_SKY'] == freq)
            # TODO: Not sure if this should be here or not...
            # (data['SIGREF'] == 0)
        )

        dataToCalibrate = data[mask]
        onMask = dataToCalibrate['CAL'] == 1
        offMask = dataToCalibrate['CAL'] == 0

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
        gain = offRow['FACTOR']
        # Need to put this BACK into an array where the only element is
        # the actual array
        # TODO: This is sooooo dumb, plz fix
        calData = gain * (offData - np.median(offData))
        return np.array([calData])

    def _getScanProcedures(self):
        "Returns a list of each scan number and its procname"
        # projName = projPath.split('/')[-1]
        path = "/".join(self.projPath.split('/')[:-1])

        scanLog = fits.getdata(os.path.join(self.projPath, "ScanLog.fits"))
        scans = []
        for row in scanLog:
            _, scan, filepath = row
            if 'GO' in filepath:
                goFile = os.path.join(path, filepath)
                goHdu = fits.open(goFile)
                h = goHdu[0].header
                scans.append((scan, h['PROCNAME'], os.path.split(filepath)[1]))
        return scans

    def _findMostRecentProcScans(self, procname, count=1):
        """
        Find the most recent scan(s) that have the given procname.
        This returns an ordered list of the most recent scan(s),
        or 0s if the proper amount of scans can't be found.
        """
        scans = self._getScanProcedures()

        procScanNums = [0] * count

        calSeqScans = [scan, file for scan, proc, file in scans
                       if scan <= self.scanNum and proc == procname]

        for i in range(min(len(calSeqScans), count)):
            procScanNums[-i - 1] = calSeqScans[-i - 1]


class WBandCalibrator(CalSeqCalibrator):
    def getGains(self):
        """
        For this scan, calculate the gains from previous calseq scan.
        This has format {"1X": 0.0, "2X": 0.0, "1Y": 0.0, "2Y": 0.0}
        """
        calSeqNum = self._findMostRecentProcScans("CALSEQ")[0][0]
        if calSeqNum:
            cal = CalibrationResults()
            cal.makeCalScan(self.projPath, calSeqNum)
            calData = cal.calData
            print("calData: ", calData)
            scanInfo, gains, tsys = calData
        else:
            # NO CalSeq scan!  Just set all gains to 1.0
            gains = {}
            for pol in ['X', 'Y']:
                for feed in [1, 2]:
                    channel = '%s%s' % (feed, pol)
                    gains[channel] = 1.0
        return gains


class ArgusCalibrator(CalSeqCalibrator):
    def getGains(self):
        """
        For this scan, calculate the gains from previous calseq scan.
        This has format {"1X": 0.0, "2X": 0.0, "1Y": 0.0, "2Y": 0.0}
        """
        calSeqNums = self._findMostRecentProcScans("VANECAL", count=2)

        if all(calSeqNums):
            cal = ArgusCalibration(
                self.projPath, calSeqNums[0][1], calSeqNums[1][1]
            )
            gains = cal.getGain()
        else:
            # Not enough VaneCal scans!  Just set all gains to 1.0
            gains = {}
            for pol in ['X', 'Y']:
                # TODO: NEED TO FIX THIS PART, OBVIOUSLY
                for feed in [10, 11]:
                    channel = '%s%s' % (feed, pol)
                    gains[channel] = 1.0
        return gains


class InvalidCalibrator(Calibrator):
    pass
