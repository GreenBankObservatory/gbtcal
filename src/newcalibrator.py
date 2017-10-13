import logging

from astropy.table import Table, Column
import numpy

from constants import POLS, POLOPTS, CALOPTS
from util import wprint
from Calibrators import TraditionalCalibrator


def initLogging():
    """Initialize the logger for this module and return it"""

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


logger = initLogging()

class Calibrator(object):
    def describe(self):
        print("My name is {}".format(self.__class__.__name__))
        print("I will be calibrating this data:")
        print(self.table)

        if self.attenuator:
            print("I will perform attenuation using: {}"
                  .format(self.attenuator.__class__.__name__))
        else:
            print("I will perform NO attenuation")

        if self.interPolCalibrator:
            print("I will perform inter-pol calibration using: {}"
                  .format(self.interPolCalibrator.__class__.__name__))
        else:
            print("I will perform NO inter-pol calibration")

        if self.interBeamCalibrator:
            print("I will perform inter-beam calibration using: {}"
                  .format(self.interBeamCalibrator.__class__.__name__))
        else:
            print("I will perform NO inter-beam calibration")


    def __init__(self, table,
                 attenuator=None,
                 interPolCalibrator=None,
                 interBeamCalibrator=None):
        self.table = table
        self.projPath = table.meta['PROJPATH']
        self.scanNum = table.meta['SCAN']
        self.attenuator = attenuator
        self.interPolCalibrator = interPolCalibrator
        self.interBeamCalibrator = interBeamCalibrator

        self.table.add_column(
            Column(name='FACTOR',
                   dtype=numpy.float64,
                   data=numpy.ones(len(self.table))
            )
        )
        self.describe()

        # import ipdb; ipdb.set_trace()
        TraditionalCalibrator(self.table).findCalFactors(self.table)

        print("-" * 70)
        print("BEGIN CALIBRATION")

    def initCalTable(self):
        calTable = Table(self.table.getUnique(['FEED', 'POLARIZE']))
        calTable.add_column(Column(name='DATA',
                                   length=len(calTable),
                                   dtype=numpy.float64,
                                   shape=self.table['DATA'].shape[1]))

        return calTable

    def attenuate(self, calTable):
        for factor in self.table.getUnique('FACTOR'):
            dataToAttenuate = self.table.query(FACTOR=factor)
            feed = dataToAttenuate['FEED'][0]
            pol = dataToAttenuate['POLARIZE'][0]
            mask = (
                (calTable['FEED'] == feed) &
                (calTable['POLARIZE'] == pol)
            )
            power = self.attenuator.attenuate(dataToAttenuate)
            print(power)
            calTable['DATA'][mask] = power

        return calTable

    def initFeedTable(self, calTable):
        feedTable = Table([numpy.unique(calTable['FEED'])])
        feedTable.add_column(Column(name='DATA',
                                    length=len(feedTable),
                                    dtype=numpy.float64,
                                    shape=calTable['DATA'].shape[1]))

        return feedTable

    def interPolCalibrate(self, feedTable, calTable):
        for row in feedTable:
            feedMask = calTable['FEED'] == row['FEED']
            filteredCalTable = calTable[feedMask]
            row['DATA'] = self.interPolCalibrator.calibrate(filteredCalTable)

    def interBeamCalibrate(self, sigFeedData, refFeedData):
        return self.interBeamCalibrator.calibrate(sigFeedData, refFeedData)

    def getCalOffData(self, calTable):
        calTable['DATA'] = self.table.query(CAL=0)['DATA']

    def getSigFeedData(self, feedTable, calTable):
        sigFeed = self.table.meta['TRCKBEAM']
        feedTable['DATA'] = calTable[calTable['FEED'] == sigFeed]['DATA']

    def calibrate(self):
        calTable = self.initCalTable()
        import ipdb; ipdb.set_trace()
        if self.attenuator:
            # If we have an attenuator, then use it. This will
            # attenuate the data and populate the calData DATA column
            logger.info("Attenuating...")
            self.attenuate(calTable)
        else:
            # If not, we just remove all of our rows that have data
            # taking while the cal diode was on
            logger.info("Removing CAL on data...")
            self.getCalOffData(calTable)
        # So, we now have a calData table with a populated DATA column,
        # ready for the next stage

        import ipdb; ipdb.set_trace()
        feedTable = self.initFeedTable(calTable)
        if self.interPolCalibrator:
            # If we have an inter-pol calibrator, then use it. This will
            # calibrate the data between the two polarizations in the
            # calTable and store the results by feed in feedTable
            self.interPolCalibrate(feedTable, calTable)
        else:
            # If we do not have an inter-pol calibrator, then the user
            # must have specified a polarization to select. We will do
            # that now...
            self.getSigFeedData(feedTable, calTable)

        import ipdb; ipdb.set_trace()
        sigFeed = self.table.meta['TRCKBEAM']
        if self.interBeamCalibrator:
            import ipdb; ipdb.set_trace()

            refFeed = self.table[self.table['FEED'] != sigFeed]['FEED'][0]
            data = self.interBeamCalibrate(feedTable[sigFeed],
                                           feedTable[refFeed])
        else:
            data = feedTable[feedTable['FEED'] == sigFeed]['DATA']
        import ipdb; ipdb.set_trace()
        return data


### Examples
# Calibrator(table, CalDiodeAttenuator, AvgPolCal, BeamSubtractCal)
# Calibrator(table, None, None, None).calibrate(Raw, X)
# Calibrator(table, None, InterPolAvg, None).calibrate(Raw, Avg)
# Calibrator(table, TotalPowerAtten, None, None).calibrate(X)
# Calibrator(table, KaSelector, TotalPowerAtten, None, None).calibrate(X)
# Calibrator(table, Generic, TotalPowerAtten, InterPolAvg, None).calibrate()
#



## How to get from GFM to this code?

# GFM: (Raw, XL)
# sel = GenericSelector(polOpt='XL')
# Calibrator(table, sel, None, None, None).calibrate()

# GFM: (TotalPower, XL)
# sel = GenericSelector(polOpt='XL')
# atten = TotalPowerAtten()
# Calibrator(table, sel, atten, None, None).calibrate()


# GFM: (TotalPower, Avg)
# sel = GenericSelector()
# atten = TotalPowerAtten()
# Calibrator(table, sel, atten, None, None).calibrate()

# GFM: (DualBeam, XL)
# sel = GenericSelector
# atten = TotalPowerAtten
# beam_sub = BeamSubtraction
# Calibrator(table, sel, atten, None, beam_sub).calibrate(polOpt='XL')


# GFM: (DualBeam, Avg)
# sel = GenericSelector
# atten = TotalPowerAtten
# pol_avg = PolAveraging
# beam_sub = BeamSubtraction
# Calibrator(table, sel, atten, pavg, beam_sub).calibrate(polOpt='Avg')

## OOF?
# GFM: (OofDualBeam, Avg)
# sel = OofSelector
# atten = OofTotalPowerAtten
# pol_avg = PolAveraging
# beam_sub = BeamSubtraction
# Calibrator(table, sel, atten, pavg, beam_sub).calibrate(polOpt='Avg')


# Ka?

# Argus?
