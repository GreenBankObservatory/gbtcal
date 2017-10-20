import sys

import numpy

# TODO: DRY
def get(name):
    current_module = sys.modules[__name__]
    try:
        return getattr(current_module, name)
    except AttributeError:
        raise AttributeError("Requested {} member {} does not exist!"
                             .format(current_module.__name__, name))

class Calibrate(object):
    def calibrate(self, rawTable, feedTable):
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
    def calibrate(self, rawTable, feedTable):
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
            print("More than two feeds provided; selecting second feed as "
                  "reference feed!")

        if trackBeam == feeds[0]:
            sig = feeds[0]
            ref = feeds[1]
        else:
            sig = feeds[1]
            ref = feeds[0]

        return sig, ref

    # def attenuate(self, table, pol=None):
    #     sigFeed, refFeed  = self.getSigRefFeeds(table)
    #     attenSigData = self.attenuate(table, pol, feed=sigFeed)
    #     attenRefData = self.attenuate(table, pol, feed=refFeed)
    #     return attenSigData, attenRefData

class OofCalibrate(InterBeamCalibrate):
    def calibrate(self, rawTable, feedTable):
        sigFeed, refFeed  = self.getSigRefFeeds(rawTable)
        sigFeedTcal = rawTable.query(FEED=sigFeed)['FACTOR'][0]
        refFeedTcal = rawTable.query(FEED=refFeed)['FACTOR'][0]

        tcalQuot = refFeedTcal / sigFeedTcal

        sigFeedCalData = feedTable.query(FEED=sigFeed)['DATA'][0]
        refFeedCalData = feedTable.query(FEED=refFeed)['DATA'][0]

        # OOF gets this backwards, so so will us
        # TODO: We are not really sure why this arrangement works, but it does
        return (refFeedCalData * tcalQuot) - sigFeedCalData


class BeamSubtractionDBA(InterBeamCalibrate):
    def calibrate(self, rawTable, feedTable):
        """Here we're just finding the difference between the two beams"""

        sigFeed, refFeed  = self.getSigRefFeeds(rawTable)
        sigFeedCalData = feedTable.query(FEED=sigFeed)['DATA'][0]
        refFeedCalData = feedTable.query(FEED=refFeed)['DATA'][0]
        # import ipdb; ipdb.set_trace()
        return sigFeedCalData - refFeedCalData

# class KaCalibrate(InterBeamCalibrate):
#     def calibrate(self, rawTable, feedTable):
#         sigFeed, refFeed  = self.getSigRefFeeds(rawTable)
#         sigData = feedTable.query(FEED=sigFeed)['DATA'][0]
#         refData = feedTable.query(FEED=refFeed)['DATA'][0]
#         # import ipdb; ipdb.set_trace()
#         return refData - sigData


class InterPolAverage(InterStreamCalibrate):
    def calibrate(self, data):
        if len(data) != 2:
            raise ValueError("InterPolAverage requires exactly two "
                             "polarizations to be given; got {}"
                             .format(len(data)))

        return numpy.mean(data['DATA'], axis=0)
