import numpy

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

    # def getTotalPower(self, rawTable, calTable):
    #     # NOTE: We expect that our table has already been filtered
    #     # to include the data from only a single feed
    #     # NOTE: This is AGNOSTIC to SIGREF. That is, it cares only about CAL
    #     onData = rawTable.getCalOnData()
    #     offData = rawTable.getCalOffData()

    #     temp = self.getAntennaTemperature(onData, offData, None)
    #     return temp

    # def attenuate(self, rawTable, calTable):
    #     calTable[calTable['FEED'] == sigFeed] =

    #     sigPower = self.getTotalPower(rawTable, calTable)
    #     refPower =

# class OofCalDiodeAttenuate(Attenuate):
#     def attenFeed(self, feedTable):
#         # TODO: Assert that these are unique
#         tcal = feedTable['FACTOR'][0]

#         onData = feedTable.getCalOnData()
#         offData = feedTable.getCalOffData()

#         return onData, offData, tcal

#     def tp(self, onData, offData):
#         count = (onData - offData).mean()
#         return 0.5 *  (onData + offData) / count

#     # def atten2TP(self, onData, offData, tcalQuot):
#     #     count = (onData - offData).mean()
#     #     return (0.5 *  (onData + offData) / count) * tcalQuot

#     def attenuate(self, table, calTable):
#         sigFeed = table.meta['TRCKBEAM']
#         refFeed = table[table['FEED'] != sigFeed]['FEED'][0]

#         pol = 'L'
#         sigFeedTable = table.query(FEED=sigFeed,
#                                    POLARIZE=pol)

#         refFeedTable = table.query(FEED=refFeed,
#                                    POLARIZE=pol)

#         sigFeedOnData, sigFeedOffData, sigFeedTcal = self.attenFeed(sigFeedTable)
#         refFeedOnData, refFeedOffData, refFeedTcal = self.attenFeed(refFeedTable)
#         sigFeedCalib = self.tp(sigFeedOnData, sigFeedOffData)
#         refFeedCalib = self.tp(refFeedOnData, refFeedOffData)

#         sigFeedTable =

#         tcalQuot = refFeedTcal / sigFeedTcal


#         # OOF gets this backwards, so so will us
#         return refFeedCalib - (sigFeedCalib * tcalQuot)
