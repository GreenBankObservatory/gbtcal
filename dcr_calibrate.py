import os
import numpy as np

from dcr_decode_astropy import getDcrDataMap


def getSupportedModes(dataKeys):
    """
    Given the physical attributes of our data, what are 
    the subset of modes supported?
    """

    # Raw should always be supported
    modes = ['Raw']

    phases = list(set([k[3] for k in dataKeys]))
    numPhases = len(phases)

    # we need more then one phase to do total Power
    if numPhases <= 1:
        # all we support is Raw then
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
    """"
    Calibrate the DCR Data from the given project path and scan
    using either the given calibration mode and polarization, or 
    the defaults
    """

    dataMap = getDcrDataMap(projPath, scanNum)

    data = dataMap['data']
    trackBeam = dataMap['trackBeam']

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

    return calibrate(data, mode, polarization, trackBeam)


def getPolKey(pol):
    "X -> XL, L -> XL, Y -> YR, R -> YR"
    pmap = {
        'X': 'XL',
        'L': 'XL',
        'Y': 'YR',
        'R': 'YR',
        'Avg': 'Avg'
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
    print("tcal, on , off", tcal, on[0], off[0])
    return getAntennaTemperature(on, off, tcal)


def calibrateDualBeam(feedTotalPowers, trackBeam, feeds):
    "Here we're just finding the difference between the two beams"

    assert len(feeds) == 2
    if trackBeam == feeds[0]:
        sig = feeds[0]
        ref = feeds[1]
    else:
        sig = feeds[1]
        ref = feeds[0]

    return feedTotalPowers[sig] - feedTotalPowers[ref]


def getRawPower(data, feed, pol, freq):
    "Raw power may be simply the data straight from the map"
    print("getRawPower", feed, pol, freq)
    sig = getSignalRawPower(data, feed, pol, freq)
    ref = getRefRawPower(data, feed, pol, freq)

    return (sig - ref) if ref is not None else sig


def getSignalRawPower(data, feed, pol, freq):
    "Simply get the raw power for the signal phase"
    phases = list(set([k[3] for k in data.keys()]))
    phase = 'Signal / No Cal' if len(phases) > 1 else phases[0]
    key = (feed, pol, freq, phase)
    raw, tcal = data[key]
    return raw


def getRefRawPower(data, feed, pol, freq):
    "Simply get the raw power for the reference phase"
    phases = list(set([k[3] for k in data.keys()]))
    refPhase = 'Reference / No Cal'
    if refPhase not in phases:
        # bail if we simply don't have that phase
        return None
    key = (feed, pol, freq, refPhase)
    raw, tcal = data[key]
    return raw


def getFreqForData(data, feed, pol):
    "Get the first data's frequency that has the given feed and polarization"
    keys = data.keys()
    # import ipdb; ipdb.set_trace()
    for f, p, freq, _ in keys:
        if f == feed and p == pol:
            return freq
    return None


def calibrate(data, mode, polarization, trackBeam, receiver):
    "Given the decoded DCR data, calibrate it for the given mode and pol"
    print("calibrating with", mode, polarization)

    # handle single pols, or averages
    allPols = list(set([k[1] for k in data.keys()]))
    if polarization == 'Avg':
        pols = allPols
    else:
        pols = [polarization]

    feeds = list(set([k[0] for k in data.keys()]))
    if trackBeam not in feeds:
        # TrackBeam must be wrong?
        # WTF!  How to know which feed to use for raw & tp?
        # we've experimented and shown that there's no happy ending here.
        # so just bail.
        return None

    # get total power for each beam that we need to
    if mode != 'DualBeam':
        # # don't waste time on more then one feed unless u need to
        feeds = [trackBeam]

    kaBeamMap = {'R': 1, 'L': 2}

    # if raw mode, couldn't be simpler
    if mode == 'Raw':
        # handles both single pol, or average
        polPowers = []
        for pol in pols:
            if receiver == 'Rcvr26_40':
                feed = kaBeamMap[pol]
            else:
                feed = trackBeam
            freq = getFreqForData(data, feed, pol)
            rawPol = getRawPower(data, feed, pol, freq)
            polPowers.append(rawPol)
        # we're done
        return sum(polPowers) / float(len(pols))

    # collect total powers from each feed
    totals = {}
    for feed in feeds:
        print("finding total power for feed:", feed)
        # make this general for both a single pol, and averaging
        polPowers = []
        for pol in pols:
            if receiver == 'Rcvr26_40':
                feed = kaBeamMap[pol]
            freq = getFreqForData(data, feed, pol)
            totalPowerPol = calibrateTotalPower(data, feed, pol, freq)
            polPowers.append(totalPowerPol)
        totals[feed] = sum(polPowers) / float(len(pols))

    if mode != 'DualBeam' or len(feeds) < 2:
        return totals[feed]
    else:
        return calibrateDualBeam(totals, trackBeam, feeds)


def calibrateAll(projPath, scanNum):
    "Returns a dict of all the possible calibrated data products"

    dataMap = getDcrDataMap(projPath, scanNum)

    data = dataMap['data']
    trackBeam = dataMap['trackBeam']
    rcvr = dataMap['receiver']

    print("**** data map summary for", rcvr)
    keys = sorted(data.keys())
    for k in keys:
        print(k, data[k][0][0], data[k][1])
    print("trackBeam: ", trackBeam)

    feeds = list(set([k[0] for k in data.keys()]))
    if trackBeam not in feeds:
        print("trackBeam not in Feeds!  Cant proces")
        return {}

    modes = getSupportedModes(data.keys())

    # TBF, Kluge: we still can't do Ka DualBeam
    if rcvr == 'Rcvr26_40':
        modes = ['Raw', 'TotalPower']

    pols = list(set([k[1] for k in data.keys()]))
    pols.append('Avg')

    # construct the options of mode and pols
    calTypes = []
    for mode in modes:
        for pol in pols:
            calTypes.append((mode, pol))

    cal = {}
    for mode, pol in calTypes:
        calData = calibrate(data, mode, pol, trackBeam, rcvr)
        key = (mode, getPolKey(pol))
        cal[key] = list(calData)

    return cal


if __name__ == '__main__':
    import sys
    projPath = sys.argv[1]
    scanNum = int(sys.argv[2])
    x = calibrateAll(projPath, scanNum)
    print("result: ", x.keys())
