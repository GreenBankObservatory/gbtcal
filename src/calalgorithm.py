import numpy

from constants import POLS, POLOPTS
from util import wprint


class Algorithm(object):
    def calibrate(self, table, pol):
        raise NotImplementedError("calibrate() must be implemented!")

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

    def getFreqForData(self, table, feed, pol):
        """
        Get the first data's frequency that has the given feed and polarization
        """
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


class RawAlgorithm(Algorithm):
    def getSignalRawPower(self, table, pol):
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

    def getRefRawPower(self, table, pol):
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

    def calibrate(self, table, pol):
        """Raw power is be simply the data straight from the table"""
        sig = self.getSignalRawPower(table, pol)
        ref = self.getRefRawPower(table, pol)
        return (sig - ref) if ref is not None else sig

class TotalPowerAlgorithm(Algorithm):

    def getAntennaTemperature(self, calOnData, calOffData, tCal):
        countsPerKelvin = (numpy.sum((calOnData - calOffData) / tCal) /
                           len(calOnData))
        Ta = 0.5 * (calOnData + calOffData) / countsPerKelvin - 0.5 * tCal
        return Ta

    def calibrate(self, table, pol, feed=None):
        # NOTE: This is AGNOSTIC to SIGREF. That is, it cares only about CAL

        # Default to Track Beam if one is not given
        if feed is None:
            feed = table.meta['TRCKBEAM']

        freq = self.getFreqForData(table, feed, pol)

        mask = (
            (table['FEED'] == feed) &
            (table['POLARIZE'] == pol) &
            (table['CENTER_SKY'] == freq)
            # TODO: Not sure if this should be here or not...
            # (table['SIGREF'] == 0)
        )

        dataToCalibrate = table[mask]

        # TODO: FIX THIS
        # ref = 1 if refPhase else 0
        ref = 0

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

# class DualBeamAlgorithm(Algorithm):
#     pass

class OofDBA(Algorithm):
    def calibrate(self, table, pol):
        sigFeed, refFeed  = self.determineTrackFeed(table)

        freq = self.getFreqForData(table, sigFeed, pol)

        sigref = 0
        cal = 1
        mask = (
            (table['FEED'] == sigFeed) &
            (table['SIGREF'] == sigref) &
            (table['CAL'] == cal) &
            (table['CENTER_SKY'] == freq) &
            (table['POLARIZE'] == pol)
        )

        onData = table[mask]['DATA']

        cal = 0
        mask = (
            (table['FEED'] == sigFeed) &
            (table['SIGREF'] == sigref) &
            (table['CAL'] == cal) &
            (table['CENTER_SKY'] == freq) &
            (table['POLARIZE'] == pol)
        )

        offData = table[mask]['DATA']
        feed1tcal = table[mask]['FACTOR'][0]


        # calculate something w/ that
        count = (onData - offData).mean()
        feed1calib = 0.5 *  (onData + offData) / count

        # get tcal for both beams
        # get on & off for ref beam
        # feeds = table.getUnique('FEED')
        # refFeed = [f for f in feeds if f != sigFeed][0]
        freq = self.getFreqForData(table, refFeed, pol)
        # rawPower = self.getRawPower(table, sigFeed, pol, freq)

        sigref = 0
        cal = 1
        mask = (
            (table['FEED'] == refFeed) &
            (table['SIGREF'] == sigref) &
            (table['CAL'] == cal) &
            (table['CENTER_SKY'] == freq) &
            (table['POLARIZE'] == pol)
        )

        onData = table[mask]['DATA']

        cal = 0
        mask = (
            (table['FEED'] == refFeed) &
            (table['SIGREF'] == sigref) &
            (table['CAL'] == cal) &
            (table['CENTER_SKY'] == freq) &
            (table['POLARIZE'] == pol)
        )

        offData = table[mask]['DATA']
        feed2tcal = table[mask]['FACTOR'][0]

        # calculate something w/ that
        count = (onData - offData).mean()
        tcalQuot = feed2tcal / feed1tcal
        feed2calib = (0.5 *  (onData + offData) / count) * tcalQuot

        # find difference
        # return feed1calib - feed2calib
        # OOF gets this backwards, so so will us
        return feed2calib - feed1calib

class BeamSubtractionDBA(TotalPowerAlgorithm):
    def calibrate(self, table, pol):
        """Here we're just finding the difference between the two beams"""
        sigFeed, refFeed = self.determineTrackFeed(table)
        sigFeedCalData = super(BeamSubtractionDBA,
                               self).calibrate(table, pol, feed=sigFeed)
        refFeedCalData = super(BeamSubtractionDBA,
                               self).calibrate(table, pol, feed=refFeed)
        return sigFeedCalData - refFeedCalData

class BeamSwitchTbOnlyDBA(TotalPowerAlgorithm):
    pass

