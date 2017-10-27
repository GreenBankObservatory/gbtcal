import logging

import numpy


logger = logging.getLogger(__name__)

class InterPolOperator(object):
    def calibrate(self, data):
        raise NotImplementedError("All InterPolOperator subclasses "
                                  "must implement calibrate()")

class InterPolAverager(InterPolOperator):
    def calibrate(self, data):
        if len(data) != 2:
            raise ValueError("InterPolAverager requires exactly two "
                             "polarizations to be given; got {}"
                             .format(len(data)))

        mean = numpy.mean(data['DATA'], axis=0)
        logger.debug("Averaged polarizations: %s", mean)
        return mean
