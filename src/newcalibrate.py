import numpy

class Calibrate(object):
    def calibrate():
        pass
    # def __init__(self, attenuator):
    #     self.attenuator = attenuator

    # def attenuate(self, table, pol, feed=None):
    #     if not self.attenuator:
    #         raise ValueError("No attenuator instance provided! "
    #                          "Only non-attenuated calibrations "
    #                          "are possible")
    #     self.attenuator.attenuate(table, pol, feed)

class InterStreamCalibrate(Calibrate):
    def calibrate():
        pass

# class IntraStreamCalibrate(Calibrate):
#     def calibrate():
#         pass

class InterBeamCalibrate(InterStreamCalibrate):
    def getSigRefFeeds(self, table):
        feeds = table.getUnique('FEED')
        trackBeam = table.meta['TRCKBEAM']

        if len(feeds) < 2:
            raise ValueError("Must have at least two feeds to determine "
                             "the tracking/reference feeds")
        if len(feeds) > 2:
            wprint("More than two feeds provided; selecting second feed as "
                   "reference feed!")

        if trackBeam == feeds[0]:
            sig = feeds[0]
            ref = feeds[1]
        else:
            sig = feeds[1]
            ref = feeds[0]

        return sig, ref

    def attenuate(self, table, pol=None):
        sigFeed, refFeed  = self.getSigRefFeeds(table)
        attenSigData = self.attenuate(table, pol, feed=sigFeed)
        attenRefData = self.attenuate(table, pol, feed=refFeed)
        return attenSigData, attenRefData

class OofCalibrate(Calibrate):
    def calibrate(self, table, pol):
        sigFeed, refFeed  = self.getSigRefFeeds(table)

        freq = self.getFreq(table, sigFeed, pol)

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
        freq = self.getFreq(table, refFeed, pol)
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


class BeamSubtractionDBA(InterBeamCalibrate):
    def calibrate(self, sigFeedCalData, refFeedCalData):
        """Here we're just finding the difference between the two beams"""
        return sigFeedCalData - refFeedCalData


class InterPolAverage(InterStreamCalibrate):
    def calibrate(self, data):
        if len(data) != 2:
            raise ValueError("InterPolAverage requires exactly two polarizations to be given")

        return numpy.mean(data['DATA'], axis=0)
