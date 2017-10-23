import numpy

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

        return numpy.mean(data['DATA'], axis=0)
