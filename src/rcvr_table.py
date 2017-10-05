from astropy.table import Column, Table
from astropy.io import ascii as astropy_ascii


class ReceiverTable(Table):
    def save(self, name, format='ecsv'):
        return astropy_ascii.write(self, name, format=format)

    @classmethod
    def load(cls, tablePath, format='ecsv'):
        table = ReceiverTable(astropy_ascii.read(tablePath,
                                                 format=format,
                                                 guess=False))
        return cls._addDerivedColumns(table)

    @classmethod
    def _addDerivedColumns(cls, table):
        calOpts = [cls._deriveCalibrationOptions(table, receiver)
                   for receiver in table['M&C Name']]
        polOpts = [cls._derivePolarizationOptions(table, receiver)
                   for receiver in table['M&C Name']]

        calOptsCol = Column(name='Cal Options',
                            data=calOpts)

        polOptsCol = Column(name='Pol Options',
                            data=polOpts)

        table.add_column(calOptsCol)
        table.add_column(polOptsCol)
        return table

    def getReceiverInfo(self, receiver):
        return self[self['M&C Name'] == receiver]

    @staticmethod
    def _deriveCalibrationOptions(table, receiver):
        receiverRow = table.getReceiverInfo(receiver)
        usableBeams = receiverRow['# Usable Beams'][0]
        calOpts = table.meta['calibrationOptions'][usableBeams]
        return [table.meta['calibrationAbbreviations'][calOptName]
                for calOptName in calOpts]

    @staticmethod
    def _derivePolarizationOptions(table, receiver):
        receiverRow = table.getReceiverInfo(receiver)
        numPols = receiverRow['# Pols'][0]
        polOpts = table.meta['polarizationOptions'][numPols]
        return [table.meta['polarizationAbbreviations'][polOptName]
                for polOptName in polOpts]

    def printFull(self):
        return self.pprint(max_lines=-1, max_width=-1)


if __name__ == '__main__':
    receiverTable = ReceiverTable.load('rcvrTable.csv')
    # print(receiverTable)
    receiverTable.printFull()
