import numpy

class Attenuate(object):
    def attenuate(self, table):
        pass



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
