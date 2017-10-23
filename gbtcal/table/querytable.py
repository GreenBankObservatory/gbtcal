from astropy.table import Table, Column, unique
import numpy

def copyTable(table, columns=None):
    """Create a new table from table with the same Columns
    but no data

    If columns is given, the new table will have only the
    provided columns"""

    if not columns:
        columnsToCopy = table.columns
    else:
        columnsToCopy = table[columns].columns

    bareColumns = []
    for name in columnsToCopy:
        oldColumn = table[name]
        newColumn = Column(name=name, dtype=oldColumn.dtype, shape=oldColumn[0].shape)
        bareColumns.append(newColumn)

    return QueryTable(bareColumns, copy=False)

class QueryTable(Table):
    def query(self, **kwargs):
        """Given a set of kwargs, query the table for rows in which
        all kwargs are True and return the result"""

        selections = kwargs
        # print(selections)
        for column, value in selections.items():
            mask = self[column] == value
            self = self[mask]
        return self

    def mask(self, **kwargs):
        selections = kwargs
        mask = numpy.array([True] * len(self))
        for column, value in selections.items():
            mask = (self[column] == value) & mask

        return mask

    def getUnique(self, columnNames):
        """Given the an iterable of column names, return their unique members"""
        return numpy.unique(self[columnNames])

    # def getUnique(self, columnNames):
    #     """Given the an iterable of column names, return their unique members"""
    #     return unique(self, keys=columnNames)[columnNames]
