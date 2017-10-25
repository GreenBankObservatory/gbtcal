import logging

import numpy


logger = logging.getLogger(__name__)

class InterPolCalibrate(object):
    def calibrate(self, data):
        raise NotImplementedError("All InterPolCalibrate subclasses "
                                  "must implement calibrate()")

class InterPolAverage(InterPolCalibrate):
    def calibrate(self, data):
        if len(data) != 2:
            raise ValueError("InterPolAverage requires exactly two "
                             "polarizations to be given; got {}"
                             .format(len(data)))

        mean = numpy.mean(data['DATA'], axis=0)
        logger.debug("Averaged polarizations: %s", mean)
        return mean
