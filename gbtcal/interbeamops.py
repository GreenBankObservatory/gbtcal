import logging


logger = logging.getLogger(__name__)


class InterBeamCalibrate(object):
    def calibrate(self, rawTable, feedTable):
        raise NotImplementedError("All InterBeamCalibrate subclasses "
                                  "must implement calibrate()")

class BeamSubtractionDBA(InterBeamCalibrate):
    def calibrate(self, rawTable, feedTable):
        """Here we're just finding the difference between the two beams"""

        sigFeed, refFeed  = rawTable.getSigAndRefFeeds()
        sigFeedCalData = feedTable.query(FEED=sigFeed)['DATA'][0]
        refFeedCalData = feedTable.query(FEED=refFeed)['DATA'][0]
        logger.debug("Subtracting %s from %s", sigFeedCalData, refFeedCalData)
        return sigFeedCalData - refFeedCalData
