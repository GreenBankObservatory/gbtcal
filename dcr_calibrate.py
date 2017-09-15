import os
import numpy as np

from dcr_decode_astropy import getDcrDataMap


def getSupportedModes(data):
    """
    Given the physical attributes of our data, what are 
    the subset of modes supported?
    """

    # Raw should always be supported
    modes = ['Raw']

    phases = np.unique(data['CAL', 'SIGREF'])
    numPhases = len(phases)

    # we need more then one phase to do total Power
    if numPhases <= 1:
        # all we support is Raw then
        return modes
    else:
        modes.append('TotalPower')

    feeds = np.unique(data['FEED'])
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

    modes = getSupportedModes(data)

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

    # NOTE: This is AGNOSTIC to SIGREF. That is, it cares only about CAL

    mask = (
        (data['FEED'] == feed) &
        (np.char.rstrip(data['POLARIZE']) == pol) &
        (data['CENTER_SKY'] == freq)
        # TODO: Not sure if this should be here or not...
        # (data['SIGREF'] == 0)
    )

    dataToCalibrate = data[mask]
    onMask = dataToCalibrate['CAL'] == 1
    offMask = dataToCalibrate['CAL'] == 0

    onRow = dataToCalibrate[onMask]
    offRow = dataToCalibrate[offMask]

    if len(onRow) != 1 or len(offRow) != 1:
        raise ValueError("Must be exactly one row each for "
                         "'on' and 'off' data")

    if onRow['TCAL'] != offRow['TCAL']:
        raise ValueError("TCAL of 'on' and 'off' data must be identical")

    # TODO: This is probably a bug in the decode code...
    # This is an array of a single array, so we extract the inner array
    onData = onRow['DATA'][0]
    offData = offRow['DATA'][0]
    # Doesn't matter which row we grab this from; they are identical
    tCal = onRow['TCAL']
    print("ON:", onData[0])
    print("OFF:", offData[0])
    print("TCAL:", tCal)
    # print(dataToCalibrate)
    # import ipdb; ipdb.set_trace()
    temp = getAntennaTemperature(onData, offData, tCal)
    print("TEMP: ", temp)
    # Need to put this BACK into an array where the only element is
    # the actual array
    # TODO: This is sooooo dumb, plz fix
    return np.array([temp])


def calibrateDualBeam(feedTotalPowers, trackBeam, feeds):
    "Here we're just finding the difference between the two beams"

    assert len(feeds) == 2
    if trackBeam == feeds[0]:
        sig, ref = feeds
    else:
        ref, sig = feeds

    return feedTotalPowers[sig] - feedTotalPowers[ref]


def getRawPower(data, feed, pol, freq):
    "Simply get the raw power, for the right phase"
    print("getRawPower", feed, pol, freq)
    phases = np.unique(data['SIGREF', 'CAL'])
    phase = (0, 0) if len(phases) > 1 else phases[0]


    sigref, cal = phase
    mask = (
        (data['FEED'] == feed) &
        (data['SIGREF'] == sigref) &
        (data['CAL'] == cal) &
        (data['CENTER_SKY'] == freq) &
        (np.char.rstrip(data['POLARIZE']) == pol)
    )

    raw = data[mask]
    assert len(raw) == 1, \
        "There should only ever be one row of data for getRawPower"
    return raw['DATA']


def getFreqForData(data, feed, pol):
    "Get the first data's frequency that has the given feed and polarization"

    mask = (
        (data['FEED'] == feed) &
        (np.char.rstrip(data['POLARIZE']) == pol)
    )

    if len(np.unique(data[mask]['CENTER_SKY'])) != 1:
        import ipdb; ipdb.set_trace()
        raise ValueError("Should be only one CENTER_SKY "
                         "for a given FEED and POLARIZE")

    return data[mask]['CENTER_SKY'][0]


def calibrate(data, mode, polarization):
    "Given the decoded DCR data, calibrate it for the given mode and pol"
    print("calibrating with", mode, polarization)

    # handle single pols, or averages
    allPols = np.unique(data['POLARIZE'])
    allPols = np.char.rstrip(allPols).tolist()

    if polarization == 'Avg':
        pols = allPols
    else:
        pols = [polarization]

    trackBeam = data.meta['TRCKBEAM']
    import ipdb; ipdb.set_trace()

    print("TRACK BEAM::: ", trackBeam)

    feeds = np.unique(data['FEED'])
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

    # if raw mode, couldn't be simpler
    if mode == 'Raw':
        # feed = feeds[0]
        # handles both single pol, or average
        polPowers = []
        for pol in pols:
            freq = getFreqForData(data, trackBeam, pol)
            rawPol = getRawPower(data, trackBeam, pol, freq)
            polPowers.append(rawPol)
        # we're done
        return sum(polPowers) / float(len(pols))

    # collect total powers from each feed
    totals = {}
    for feed in feeds:
        # make this general for both a single pol, and averaging
        polPowers = []
        for pol in pols:
            freq = getFreqForData(data, feed, pol)
            totalPowerPol = calibrateTotalPower(data, feed, pol, freq)
            polPowers.append(totalPowerPol)
        totals[feed] = sum(polPowers) / float(len(pols))

    if mode != 'DualBeam' or len(feeds) < 2:
        return totals[feeds[0]]
    else:
        return calibrateDualBeam(totals, trackBeam, feeds)


def calibrateAll(projPath, scanNum):
    "Returns a dict of all the possible calibrated data products"

    dataMap = getDcrDataMap(projPath, scanNum)

    # data = dataMap['data']
    # trackBeam = dataMap['trackBeam']
    # rcvr = dataMap['receiver']

    # print("**** data map summary for", rcvr)
    # keys = sorted(data.keys())
    # for k in keys:
    #     print(k, data[k][0][0], data[k][1])
    # print("trackBeam: ", trackBeam)


    # feeds = list(set([k[0] for k in data.keys()]))
    feeds = np.unique(dataMap['FEED'])
    trackBeam = dataMap.meta['TRCKBEAM']
    if trackBeam not in feeds:
        print("trackBeam not in Feeds!  Cant proces")
        return {}

    modes = getSupportedModes(dataMap)

    pols = np.unique(dataMap['POLARIZE'])
    pols = np.char.rstrip(pols).tolist()
    pols.append('Avg')

    # construct the options of mode and pols
    calTypes = []
    for mode in modes:
        for pol in pols:
            calTypes.append((mode, pol))

    rcvr = dataMap['RECEIVER'][0]
    if rcvr == "Rcvr26_40":
        # Ka rcvr only suppports feeds, pols: (1, R), (2, L)
        # so we can't do all the same cal types as everyone else
        kaPolMap = {1: 'R', 2: 'L'}
        calTypes = [
            ('Raw', kaPolMap[trackBeam]),
            ('TotalPower', kaPolMap[trackBeam])
        ]

    cal = {}
    for mode, pol in calTypes:
        calData = calibrate(dataMap, mode, pol)
        # import ipdb; ipdb.set_trace()
        key = (mode, getPolKey(pol))
        cal[key] = list(calData)

    # import ipdb; ipdb.set_trace()
    return cal


if __name__ == '__main__':
    import sys
    projPath = sys.argv[1]
    scanNum = int(sys.argv[2])
    x = calibrateAll(projPath, scanNum)
    print("result: ", x.keys())
