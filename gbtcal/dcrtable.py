import logging
import os

from astropy.table import Column, hstack, vstack
import numpy

from table.stripped_table import StrippedTable


logger = logging.getLogger(__name__)

class DcrTable(StrippedTable):
    """A Table representing DCR/IF data from a single scan
    """
    @classmethod
    def read(cls, dcrHduList, ifHduList):
        """Given DCR and IF FITS objects, consolidate their data and
        return the resultant Table as a DcrTable
        """
        return cls(cls._consolidateFitsData(dcrHduList, ifHduList))

    def getUniquePhases(self):
        """Return a `numpy.array` of (SIGREF, CAL) tuples representing
        all of the unique pairings of SIGREF and CAL within this Table.
        Each pairing represents a phase.
        SIGREF = 0 => Signal Beam
        SIGREF = 1 => Reference Beam
        CAL = 0 => Cal diode off
        CAL = 1 => Cal diode on
        """
        return self.getUnique('SIGREF', 'CAL')

    def getUniqueFeeds(self):
        return self.getUnique('FEED')

    def getUniquePolarizations(self):
        return self.getUnique('POLARIZE')

    def getTrackBeam(self):
        """Return an `int` representing the Track Beam that has been selected
        for this scan
        """
        return self.meta['TRCKBEAM']

    def getReceiver(self):
        """Return a `str` indicating the receiver that took the data
        for this scan
        """
        return self.meta['RECEIVER']

    def getDataForPhase(self, signal, cal):
        """Given a signal and cal, return the phase data associated
        with it. signal = True => Signal; signal = False => reference
        """
        # Invert the given signal value -- if the user asks for the
        # signal beam, that is actually SIGREF = 0
        sigref = 0 if signal else 1
        phaseMask = (
            (self['SIGREF'] == sigref) &
            (self['CAL'] == int(cal))
        )
        return self[phaseMask]

    def getSigAndRefFeeds(self):
        feeds = self.getUnique('FEED')
        trackBeam = self.getTrackBeam()

        if len(feeds) < 2:
            raise ValueError("Must have at least two feeds to determine "
                             "the tracking/reference feeds")
        if len(feeds) > 2:
            logger.warning("More than two feeds provided; selecting second feed as "
                           "reference feed!")

        if trackBeam == feeds[0]:
            logger.debug("Track beam is the first feed")
            sig = feeds[0]
            ref = feeds[1]
        else:
            logger.debug("Track beam is NOT the first feed")
            sig = feeds[1]
            ref = feeds[0]

        logger.debug("Got sig: %s; ref: %s", sig, ref)

        return sig, ref

    @staticmethod
    def getTableByName(hduList, tableName):
        # TODO: Does not work if there are multiple tables of the same name
        """Given a FITS file HDU list and the name of a table, return its Astropy
        Table representation"""
        table = StrippedTable.read(hduList[hduList.index_of(tableName)])
        return table

    @classmethod
    def getIfDataByBackend(cls, ifHduList, backend='DCR'):
        """Given an IF FITS file, return a table containing only rows for
        the specified backend"""
        ifTable = cls.getTableByName(ifHduList, 'IF')

        # First, we filter out all non-DCR backends
        # Create a 'mask' -- this is an array of booleans that
        # indicate which rows are associated with the DCR backend
        # NOTE: We need to strip whitespace from this column --
        # this is because our FITS files pad each charfield
        # https://github.com/astropy/astropy/issues/2608
        mask = numpy.char.rstrip(ifTable['BACKEND']) == backend
        # We then filter out these indices
        dcrData = ifTable[mask]
        return dcrData

    @classmethod
    def _consolidateFitsData(cls, dcrHdu, ifHdu):
        """Given DCR and IF HDU objects, pull out the information needed
        to perform calibration into a single Astropy Table, then return it"""

        # STATE describes the phases in use
        dcrStateTable = cls.getTableByName(dcrHdu, 'STATE')
        # DATA contains the actual data recorded by the DCR
        dcrDataTable = cls.getTableByName(dcrHdu, 'DATA')

        # How many unique CAL states are there?
        calStates = numpy.unique(dcrStateTable['CAL'])
        # There should be only 1 or 2 possible states
        if list(calStates) not in [[0], [1], [0, 1]]:
            raise ValueError("Invalid CAL states detected in DCR.RECEIVER.CAL: {}"
                             .format(calStates))

        # How many unique SIGREF states are there?
        sigRefStates = numpy.unique(dcrStateTable['SIGREF'])
        # There should be only 1 or 2 possible states
        if list(sigRefStates) not in [[0], [1], [0, 1]]:
            raise ValueError("Invalid SIGREF states detected in "
                             "DCR.RECEIVER.SIGREF: {}".format(sigRefStates))

        # DCR data from IF table
        ifDcrDataTable = cls.getIfDataByBackend(ifHdu)

        if len(numpy.unique(ifDcrDataTable['RECEIVER'])) != 1:
            raise ValueError("There must only be one RECEIVER per scan!")

        ifDcrDataTable.meta['RECEIVER'] = ifDcrDataTable['RECEIVER'][0]
        # Strip out unneeded/misleading columns
        filteredIfTable = ifDcrDataTable[
            'FEED', 'RECEPTOR', 'POLARIZE', 'CENTER_SKY',
            'BANDWDTH', 'PORT', 'HIGH_CAL'
        ]

        # Each of these rows actually has a maximum of four possible states:
        # | `SIGREF` | `CAL` |      Phase key       | Phase index |
        # |----------|-------|----------------------|-------------|
        # |        0 |     0 | `Signal / No Cal`    |           0 |
        # |        0 |     1 | `Signal / Cal`       |           1 |
        # |        1 |     0 | `Reference / No Cal` |           2 |
        # |        1 |     1 | `Reference / Cal`    |           3 |

        # So, let's get the number of states for this specific dataset
        # by querying the DCR STATE table. Note that this is a scalar value
        # that indicates how many phases the data from each port has been
        # taken during
        numPhasesPerPort = len(numpy.unique(dcrStateTable['SIGREF', 'CAL']))

        # Then we can stack our IF table n times, where n is numPhasesPerPort
        filteredIfTable = vstack([filteredIfTable] * numPhasesPerPort)

        filteredIfTable.sort('PORT')

        # We now have a table that is the correct final size.
        # But, it does not yet have the SIGREF and CAL columns

        # Before we add those, we need to make them the right length.
        # We do that by stacking a slice of the state table containing only
        # those two columns n times, where n is the number of rows in the IF
        # DCR table.
        try:
            expandedStateTable = vstack([dcrStateTable['SIGREF', 'CAL']] *
                                        len(ifDcrDataTable))
        except TypeError:
            logger.error("Could not stack DCR table. Is length of ifDcrDataTable 0? {}"
                   .format(len(ifDcrDataTable)))
            logger.error(ifDcrDataTable)
            raise

        # Delete this meta key; we don't need it and it
        # results in a warning
        del expandedStateTable.meta['EXTNAME']
        # We now have two tables, both the same length, and they can be simply
        # stacked together horizontally.
        filteredIfTable = hstack([filteredIfTable, expandedStateTable])

        # We now have a table that maps physical attributes to the different
        # states in which data was taken. That is, for each feed we have rows
        # that map it to the various SIGREF and CAL states that were active at
        # some point during the scan.
        # So, we now need to map these physical attributes to the actual data!

        # Get the sets of unique SIGREF and CAL states. Note that this could
        # _probably_ be done by simply grabbing the whole column from
        # dcrStateTable, but this way we guarantee uniqueness.
        uniquePorts = numpy.unique(filteredIfTable['PORT'])
        uniqueSigRefStates = numpy.unique(filteredIfTable['SIGREF'])
        uniqueCalStates = numpy.unique(filteredIfTable['CAL'])

        phaseStateTable = dcrStateTable['SIGREF', 'CAL']
        phaseStateTable.add_column(Column(name='PHASE',
                                          data=numpy.arange(len(phaseStateTable))))

        filteredIfTable.add_column(Column(
            name='DATA',
            dtype=dcrDataTable['DATA'].dtype,
            shape=dcrDataTable['DATA'].shape[0],
            length=len(filteredIfTable)
        ))

        # This is a reasonable assert to make, but it will fail when the IF FITS
        # only has a *subset* of the ports used by the DCR.  Sparrow ignores ports
        # NOT specified by the IF FITS file, wo we'll do the same
        #assert len(uniquePorts) == dcrDataTable['DATA'].shape[1]
        if len(uniquePorts) != dcrDataTable['DATA'].shape[1]:
            logger.warning("IF ports are only a subset of DCR ports used")
        # TODO: I wonder if there is a way to avoid looping here altogether?
        for portIndex, port in enumerate([port + 1 for port in uniquePorts]):
            # TODO: Combine these into one?
            for sigRefStateIndex, sigRefState in enumerate(uniqueSigRefStates):
                for calStateIndex, calState in enumerate(uniqueCalStates):
                    phaseMask = (
                        (phaseStateTable['SIGREF'] == sigRefState) &
                        (phaseStateTable['CAL'] == calState)
                    )
                    # Assert that the mask doesn't match more than one row
                    if numpy.count_nonzero(phaseMask) != 1:
                        raise ValueError("PHASE could not be unambiguously "
                                         "determined from given SIGREF ({}) "
                                         "and CAL ({})"
                                         .format(sigRefState, calState))
                    phase = phaseStateTable[phaseMask]['PHASE'][0]
                    # Calculate the index of our 1D column from where we are
                    # in our 3D data
                    dataColumnIndex = (
                        (portIndex * (len(uniqueSigRefStates) * len(uniqueCalStates))) +
                        (sigRefStateIndex * len(uniqueCalStates)) +
                        calStateIndex
                    )
                    # Slice out our data. We want data from every row of DATA (::),
                    # but we only want the data in the nth dimension of the
                    # mth dimension, where m = portIndex and n = phase
                    dataRow = dcrDataTable['DATA'][::, portIndex, phase]
                    filteredIfTable['DATA'][dataColumnIndex] = dataRow

        projPath = os.path.dirname(os.path.dirname(dcrHdu.filename()))
        filteredIfTable.meta['PROJPATH'] = os.path.realpath(projPath)

        return filteredIfTable

    def _getCalData(self, calState):
        data = self.query(CAL=calState)['DATA']
        if len(data) != 1:
            import ipdb; ipdb.set_trace()
            raise ValueError("Cannot unambiguously retrieve CAL state; "
                             "expected 1 row but got {}!".format(len(data)))

        return data[0]

    def getCalOnData(self):
        return self._getCalData(calState=1)

    def getCalOffData(self):
        return self._getCalData(calState=0)

    def getFactor(self):
        if 'FACTOR' not in self.columns:
            raise ValueError('FACTOR Column has not yet been added!')

        if len(self.getUnique('FACTOR')) != 1:
            raise ValueError("Cannot unambiguously determine FACTOR; "
                             "there are multiple values present!")
        return self['FACTOR'][0]

    def getTrackFeedData(self):
        return self.query(FEED=self.getTrackBeam())
