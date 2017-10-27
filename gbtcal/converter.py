import logging

import numpy


logger = logging.getLogger(__name__)


class CountsToKelvinConverter(object):
    """Convert from raw counts/voltages to kelvin

    "Counts" are how power levels are actually recorded by the
    telescope instrumentation. To be astronomically useful, these
    are almost always need to be converted to kelvin via some
    calibration method."""

    def convertCountsToKelvin(self, table):
        raise NotImplementedError("convertCountsToKelvin() must be defined for all "
                                  "CountsToKelvinConverter subclasses!")

class CalSeqConverter(CountsToKelvinConverter):
    """Convert from counts to kelvin via a "cal sequence"

    A cal sequence is typically created by a dedicated calibration
    scan, and can then be used to convert from counts to kelvin."""

    def getTotalPower(self, table):
        """Total power for External Cals is just the off with a gain."""
        offTable = table

        if len(offTable) != 1:
            raise ValueError("Must be exactly one row for 'off' data")

        # This is an array of a single array, so we extract the inner array
        offData = offTable['DATA'][0]
        # Doesn't matter which row we grab this from; they are identical
        gain = offTable['FACTOR']
        # Need to put this BACK into an array where the only element is
        # the actual array
        calData = gain * (offData - numpy.median(offData))
        return calData

    def convertCountsToKelvin(self, table):
        return self.getTotalPower(table)


class CalDiodeConverter(CountsToKelvinConverter):
    """Convert from counts to kelvin by comparing data taken
    when a calibration diode was on/off"""

    def getAntennaTemperature(self, calOnData, calOffData, tCal):
        """Perform the actual counts -> kelvin conversion"""

        countsPerKelvin = (numpy.sum((calOnData - calOffData) / tCal) /
                           len(calOnData))
        Ta = 0.5 * (calOnData + calOffData) / countsPerKelvin - 0.5 * tCal
        logger.debug("Got antenna temperatures: [%f ... %f]", Ta[0], Ta[-1])
        return Ta

    def getTotalPower(self, table):
        """Gather data from table in order to convert counts -> kelvin"""

        # NOTE: We expect that our table has already been filtered
        # to include the data from only a single feed
        # NOTE: This is AGNOSTIC to SIGREF. That is, it cares only about CAL
        onData = table.getCalOnData()
        offData = table.getCalOffData()

        tCal = table.getFactor()
        temp = self.getAntennaTemperature(onData, offData, tCal)
        return temp

    def convertCountsToKelvin(self, table):
        return self.getTotalPower(table)
