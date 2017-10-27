import logging


logger = logging.getLogger(__name__)


class InterBeamOperator(object):
    def calibrate(self, table):
        raise NotImplementedError("All InterBeamOperator subclasses "
                                  "must implement calibrate()")

class BeamSubtractor(InterBeamOperator):
    def calibrate(self, table):
        """Here we're just finding the difference between the two beams"""

        sigFeed = table.meta['SIGFEED']
        refFeed = table.meta['REFFEED']
        # TODO: Do we need to select on pol?
        sigFeedCalData = table.query(FEED=sigFeed)['DATA'][0]
        refFeedCalData = table.query(FEED=refFeed)['DATA'][0]
        logger.debug("Subtracting sig-feed data from ref-feed data")
        return sigFeedCalData - refFeedCalData
