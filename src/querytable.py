from astropy.table import Table


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
