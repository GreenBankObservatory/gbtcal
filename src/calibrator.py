from astropy.table import Column, Table, hstack, vstack
import numpy
from dcr_table import stripTable
from dcr_decode_astropy import getFitsForScan, getTcal, getRcvrCalTable
from dcr_calibrate import calibrateTotalPower, calibrateDualBeam, getFreqForData

def calibrateDualBeam(feedTotalPowers, trackBeam, feeds):
    "Here we're just finding the difference between the two beams"

    assert len(feeds) == 2
    if trackBeam == feeds[0]:
        sig, ref = feeds
    else:
        ref, sig = feeds

    return feedTotalPowers[sig] - feedTotalPowers[ref]


class Calibrator(object):
    def __init__(self, receiverInfoTable, ifDcrDataTable):
        self._receiverInfoTable = receiverInfoTable
        self._ifDcrDataTable = ifDcrDataTable
        self.projPath = ifDcrDataTable.meta['PROJPATH']
        self.scanNum = ifDcrDataTable.meta['SCAN']

    @property
    def receiverInfoTable(self):
        return self._receiverInfoTable

    @property
    def ifDcrDataTable(self):
        return self._ifDcrDataTable

    def findCalFactors(self, data):
        raise NotImplementedError("findCalFactors() must be implemented for "
                                  "all Calibrator subclasses!")

    def doMath(self, dataTable, polOption, refBeam):
        raise NotImplementedError("doMath() must be implemented for "
                                  "all Calibrator subclasses!")

    def calibrate(self, polOption='Both', doGain=True, refBeam=False):
        newTable = self.ifDcrDataTable.copy()

        # TODO: Should this be done here? Opens the possibility of
        # some error silently preventing the replacement
        # of this column with the _real_ factors...
        newTable.add_column(
            Column(name='FACTOR',
                   dtype=numpy.float64,
                   data=numpy.ones(len(newTable))))
        if doGain:
            self.findCalFactors(newTable)

        return self.doMath(newTable, polOption, refBeam)


class TraditionalCalibrator(Calibrator):
    def findCalFactors(self, data):
        print("Looking at tCals and stuff")

        receiver = data['RECEIVER'][0]

        fitsForScan = getFitsForScan(self.projPath, self.scanNum)
        rcvrCalHduList = fitsForScan[receiver]
        rcvrCalTable = getRcvrCalTable(rcvrCalHduList)

        # TODO: Double check this assumption
        uniqueRows = numpy.unique(data['FEED', 'POLARIZE',
                                       'CENTER_SKY', 'BANDWDTH',
                                       'HIGH_CAL'])
        for feed, pol, centerSkyFreq, bandwidth, highCal in uniqueRows:
            mask = ((data['FEED'] == feed) &
                    (data['POLARIZE'] == pol) &
                    (data['CENTER_SKY'] == centerSkyFreq) &
                    (data['BANDWDTH'] == bandwidth) &
                    (data['HIGH_CAL'] == highCal))

            maskedData = data[mask]

            if len(numpy.unique(maskedData['RECEPTOR'])) != 1:
                raise ValueError("The rows in the receiver calibration file "
                                 "must all be unique for all "
                                 "feed/polarization/frequency groupings.")

            receptor = maskedData['RECEPTOR'][0]

            tCal = getTcal(rcvrCalTable, feed, receptor, pol,
                           highCal, centerSkyFreq, bandwidth)
            for row in data[mask]:
                # TODO: Cleaner way of doing this?
                data[row['INDEX']]['FACTOR'] = tCal

    def doMath(self, dataTable, polOption, refBeam):
        # TODO: Validate that polOption and refBeam choices are allowable
        # for the current dataTable. I.E., refBeam selected requires there
        # to be two feeds. polOption="Both", requires two polarizations.
        # And, if there is only one polarization ("X"), polOption can't be
        # "Y". We should figure out a way to apply default polOptions in a
        # receiver table.
        # This is the same for all "Traditional" calibrators
        print("Doing math for trad cal")


        # handle single pols, or averages
        allPols = numpy.unique(dataTable['POLARIZE'])
        allPols = allPols.tolist()

        if polOption == 'Both':
            pols = allPols
        else:
            pols = [polOption]

        trackBeam = dataTable.meta['TRCKBEAM']

        print("TRACK BEAM::: ", trackBeam)

        feeds = numpy.unique(dataTable['FEED'])
        if trackBeam not in feeds:
            # TrackBeam must be wrong?
            # WTF!  How to know which feed to use for raw & tp?
            # we've experimented and shown that there's no happy ending here.
            # so just bail.
            return None

        feeds = [trackBeam]

        # collect total powers from each feed
        totals = {}
        for feed in feeds:
            # make this general for both a single pol, and averaging
            polPowers = []
            for pol in pols:
                freq = getFreqForData(dataTable, feed, pol)
                totalPowerPol = calibrateTotalPower(dataTable, feed, pol, freq)
                polPowers.append(totalPowerPol)
            totals[feed] = sum(polPowers) / float(len(pols))

        # If refBeam is True, then Dual Beam
        if refBeam:
            if numpy.unique(dataTable['FEED']) != 2:
                raise ValueError("Data table must contain exactly two "
                                 "unique feeds to perform "
                                 "dual beam calibration")

            return calibrateDualBeam(totals, trackBeam, feeds)

            # dual beam
        else:
            # total power
            pass


class CalSeqCalibrator(Calibrator):
    def doMath(self, dataTable, polOption, refBeam):
        # This is the same for all "Cal Seq" calibrators -- right now
        # just W band and Argus
        print("Doing math for Cal Seq calibration")


class WBandCalibrator(CalSeqCalibrator):
    def findCalFactors(self):
        print("Finding cal factors for W band using Cal Seq and stuff")


class ArgusCalibrator(CalSeqCalibrator):
    def findCalFactors(self):
        print("Finding cal factors for Argus doing whatever it does")
