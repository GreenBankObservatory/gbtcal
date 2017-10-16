from astropy.table import Column
import numpy

from querytable import QueryTable

class StrippedTable(QueryTable):
    """An implementation of Table that strips all right padding from
    string columns when calling read()
    """
    @staticmethod
    def _stripTable(table):
        """Given an `astropy.table`, strip all of its string-type columns
        of any right-padding, in place.
        """
        for column in table.columns.values():
            # If the type of this column is String or Unicode...
            if column.dtype.char in ['S', 'U']:
                # ...replace its data with a copy in which the whitespace
                # has been stripped from the right side
                strippedColumn = Column(name=column.name,
                                        data=numpy.char.rstrip(column))
                # print("Replacing column {} with stripped version"
                #       .format(column.name))
                table.replace_column(column.name, strippedColumn)

    @classmethod
    def read(cls, *args, **kwargs):
        # Get a table instance using Table's read()
        table = super(StrippedTable, cls).read(*args, **kwargs)
        # Strip the table in place
        cls._stripTable(table)
        # Return the Table as a StrippedTable
        return cls(table)


    def getUnique(self, columnNames):
        """Given the an iterable of column names, return their unique members"""
        return numpy.unique(self[columnNames])

