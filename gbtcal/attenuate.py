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

class Attenuate(object):
    def attenuate(self, table):
        pass

class CalSeqAttenuate(Attenuate):
    def getTotalPower(self, table):
        """Total power for External Cals is just the off with a gain."""
        # offTable = table.query(FEED=feed, POLARIZE=pol, CENTER_SKY=freq)
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

class OofCalDiodeAttenuate(CalDiodeAttenuate):
    def getAntennaTemperature(self, calOnData, calOffData, tCal):
        # NOTE: tCal is note used here! It will be used later on
        count = (calOnData - calOffData).mean()
        return 0.5 *  (calOnData + calOffData) / count
