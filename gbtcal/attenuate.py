import logging

import numpy


logger = logging.getLogger(__name__)


class Attenuate(object):
    def attenuate(self, table):
        raise NotImplementedError("attenuate() must be defined for all "
                                  "Attenuate subclasses!")

class CalSeqAttenuate(Attenuate):
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

    def attenuate(self, table):
        return self.getTotalPower(table)


class CalDiodeAttenuate(Attenuate):
    def getAntennaTemperature(self, calOnData, calOffData, tCal):
        countsPerKelvin = (numpy.sum((calOnData - calOffData) / tCal) /
                           len(calOnData))
        Ta = 0.5 * (calOnData + calOffData) / countsPerKelvin - 0.5 * tCal
        logger.debug("Got antenna temperatures: %s", Ta)
        return Ta

    def getTotalPower(self, table):
        # NOTE: We expect that our table has already been filtered
        # to include the data from only a single feed
        # NOTE: This is AGNOSTIC to SIGREF. That is, it cares only about CAL
        onData = table.getCalOnData()
        offData = table.getCalOffData()

        tCal = table.getFactor()
        temp = self.getAntennaTemperature(onData, offData, tCal)
        return temp

    def attenuate(self, table):
        return self.getTotalPower(table)
