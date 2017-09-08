
import numpy as np

from dcr_decode_astropy import getDcrDataMap


def getSupportedModes(dataKeys):
    modes = ['Raw']

    phases = list(set([k[3] for k in dataKeys]))
    numPhases = len(phases)

    # we need more then one phase to do total Power
    if numPhases <= 1:
        return modes
    else:
        modes.append('TotalPower')

    feeds = list(set([k[0] for k in dataKeys]))
    numFeeds = len(feeds)

    # we need more then one feed for dual beam
    if numFeeds <= 1:
        return modes
    else:
        modes.append('DualBeam')

    return modes


def calibrateDcrData(projPath, scanNum, mode=None, polarization=None):

    data = getDcrDataMap(projPath, scanNum)

    modes = getSupportedModes(data.keys())

    if mode is not None and mode not in modes:
        raise ValueError("Mode %s not supported" % mode)

    pols = list(set([k[1] for k in data.keys()]))

    if polarization != 'Avg':
        if polarization is not None and polarization not in pols:
            raise ValueError("Polarization %s not supported" % mode)

    # use the highest mode as default
    if mode is None:
        mode = modes[-1]

    # just pick a pol if you have to
    if polarization is None:
        polarization = pols[0]
    else:
        # TBD: map 'XL' to 'X' or 'L'
        pass

    # TBF:
    trackBeam = 1

    return calibrate(data, mode, polarization, trackBeam)


def getPolKey(pol):
    "X -> XL, L -> XL, Y -> YR, R -> YR"
    pmap = {
        'X': 'XL',
        'L': 'XL',
        'Y': 'YR',
        'R': 'YR',
    }
    return pmap[pol]


def getAntennaTemperature(calOnData, calOffData, tCal):
    countsPerKelvin = (np.sum((calOnData - calOffData) / tCal) /
                       len(calOnData))
    Ta = 0.5 * (calOnData + calOffData) / countsPerKelvin - 0.5 * tCal
    return Ta


def calibrateTotalPower(data, feed, pol, freq):

    # TBF: handle sigref = 1
    onKey = (feed, pol, freq, 'Signal / Cal')
    offKey = (feed, pol, freq, 'Signal / No Cal')

    on, tcal = data[onKey]
    off, tcal = data[offKey]
    print("tcal", tcal)
    return getAntennaTemperature(on, off, tcal)


def calibrateDualBeam(feedTotalPowers, trackBeam):

    if trackBeam == 1:
        return feedTotalPowers[1] - feedTotalPowers[2]
    else:
        return feedTotalPowers[2] - feedTotalPowers[1]


def calibrate(data, mode, polarization, trackBeam):
    print("calibrating with", mode, polarization)

    # TBD: always just use the first freq?
    allFreqs = list(set([k[2] for k in data.keys()]))
    freq = allFreqs[0]

    # handle single pols, or averages
    allPols = list(set([k[1] for k in data.keys()]))
    if polarization == 'Avg':
        pols = allPols
    else:
        pols = [polarization]

    # get total power for each beam that we need to
    feeds = list(set([k[0] for k in data.keys()]))
    if mode != 'DualBeam':
        # don't waste time on more then one feed unless u need to
        feeds = [feeds[0]]

    totals = {}
    for feed in feeds:
        # make this general for both a single pol, and averaging
        polPowers = []
        for pol in pols:
            totalPowerPol = calibrateTotalPower(data, feed, pol, freq)
            polPowers.append(totalPowerPol)
        totals[feed] = sum(polPowers) / float(len(pols))

    if mode != 'DualBeam' or len(feeds) < 2:
        return totals[feed]
    else:
        return calibrateDualBeam(totals, trackBeam)


if __name__ == '__main__':
    import sys
    projPath = sys.argv[1]
    scanNum = int(sys.argv[2])
    x = calibrateDcrData(projPath, scanNum)
    print("result: ", x)
