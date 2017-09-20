import os
import numpy as np
from astropy.io import fits

from dcr_decode_astropy import getDcrDataMap
from CalibrationResults import CalibrationResults

CALSEQ_RCVRS = ["Rcvr68_92"]


def getSupportedModes(dataKeys, receiver=None):
    """
    Given the physical attributes of our data, what are 
    the subset of modes supported?
    """

    # Raw should always be supported
    modes = ['Raw']

    phases = list(set([k[3] for k in dataKeys]))
    numPhases = len(phases)

    # we need more then one phase to do total Power
    if numPhases <= 1 and receiver not in CALSEQ_RCVRS:
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
    rx = dataMap['receiver']

    modes = getSupportedModes(data.keys(), receiver=rx)

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


def determineTrackFeed(trackBeam, feeds):
    assert len(feeds) == 2
    if trackBeam == feeds[0]:
        sig = feeds[0]
        ref = feeds[1]
    else:
        sig = feeds[1]
        ref = feeds[0]
    return sig, ref


def calibrateBeamSwitchedTBOnly(data, trackBeam, feeds):
    "Calibrating with the four phases of just the Tracking Beam"

    sigFeed, refFeed = determineTrackFeed(trackBeam, feeds)

    # get the total power of the tracking beam's signal phases
    kaPolMap = {1: 'R', 2: 'L'}
    pol = kaPolMap[sigFeed]

    freq = getFreqForData(data, sigFeed, pol)

    sigOnKey = (sigFeed, pol, freq, 'Signal / Cal')
    sigOffKey = (sigFeed, pol, freq, 'Signal / No Cal')

    sigOn, tcal = data[sigOnKey]
    sigOff, tcal = data[sigOffKey]

    taSig = getAntennaTemperature(sigOn, sigOff, tcal)

    # get the total power of the tracking beam's ref phases
    refOnKey = (sigFeed, pol, freq, 'Reference / Cal')
    refOffKey = (sigFeed, pol, freq, 'Reference / No Cal')

    refOn, _ = data[refOnKey]
    refOff, _ = data[refOffKey]

    # Note that we need to use the tcal for the ref. beam.
    pol = kaPolMap[refFeed]
    freq = getFreqForData(data, refFeed, pol)
    aKeyForRef = (refFeed, pol, freq, 'Signal / No Cal')
    _, refCal = data[aKeyForRef]

    taRef = getAntennaTemperature(refOn, refOff, refCal)

    return taSig - taRef


# We still don't know how to do this properly for Ka data
def calibrateBeamSwitched(data, pol, trackBeam, feeds):
    "Calibrating with four phases, two beams"

    sigFeed, refFeed = determineTrackFeed(trackBeam, feeds)

    kaPolMap = {1: 'R', 2: 'L'}

    sigPol = kaPolMap[sigFeed]
    refPol = kaPolMap[refFeed]

    sigFreq = getFreqForData(data, sigFeed, sigPol)
    refFreq = getFreqForData(data, refFeed, refPol)

    # get the two Tcals that apply to each beam
    sigKey = (sigFeed, sigPol, sigFreq, 'Signal / No Cal')
    _, sigTcal = data[sigKey]
    refKey = (refFeed, refPol, refFreq, 'Signal / No Cal')
    _, refTcal = data[refKey]

    taSig1, taRef1 = getSigRefAntTemperature(data,
                                             sigPol,
                                             sigFreq,
                                             sigFeed,
                                             sigTcal,
                                             refTcal)
    taSig2, taRef2 = getSigRefAntTemperature(data,
                                             refPol,
                                             refFreq,
                                             refFeed,
                                             refTcal,
                                             sigTcal)

    print "taSig1, taRef1", taSig1[0], taRef1[0]
    print "taSig2, taRef2", taSig2[0], taRef2[0]

    return 0.5 * ((taSig1 - taRef1) + (taRef2 - taSig2))


def getSigRefAntTemperature(data, pol, freq, feed, sigTcal, refTcal):
    "For the given feed, get Ant. Temp. using all 4 phases"
    print "getSigRefAntTemperature for", pol, freq, feed

    sigOnKey = (feed, pol, freq, 'Signal / Cal')
    sigOffKey = (feed, pol, freq, 'Signal / No Cal')

    refOnKey = (feed, pol, freq, 'Reference / Cal')
    refOffKey = (feed, pol, freq, 'Reference / No Cal')

    sigOn, _ = data[sigOnKey]
    sigOff, _ = data[sigOffKey]
    refOn, _ = data[refOnKey]
    refOff, _ = data[refOffKey]
    print "sig on, off, ref on off for beam:", feed
    print sigOn[0], sigOff[0], refOn[0], refOff[0]

    taSig = getAntennaTemperature(sigOn, sigOff, sigTcal)
    taRef = getAntennaTemperature(refOn, refOff, refTcal)

    return taSig, taRef


def calibrateDualBeam(feedTotalPowers, trackBeam, feeds):
    "Here we're just finding the difference between the two beams"

    sig, ref = determineTrackFeed(trackBeam, feeds)

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


def calibrate(data, mode, polarization, trackBeam, receiver, gains=None):
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
    if mode not in ['DualBeam', 'BeamSwitch', 'BeamSwitchedTBOnly']:
        # # don't waste time on more then one feed unless u need to
        feeds = [trackBeam]

    kaBeamMap = {'R': 1, 'L': 2}

    # if raw mode, couldn't be simpler
    if mode == 'Raw':
        # handles both single pol, or average
        polPowers = []
        for pol in pols:
            # Ka only has one pol per feed
            if receiver == 'Rcvr26_40':
                feed = kaBeamMap[pol]
            else:
                feed = trackBeam
            freq = getFreqForData(data, feed, pol)
            rawPol = getRawPower(data, feed, pol, freq)
            polPowers.append(rawPol)
        # we're done
        return sum(polPowers) / float(len(pols))

    # This is only supported by Ka apparently
    if mode == 'BeamSwitchedTBOnly':
        # to bail here
        return calibrateBeamSwitchedTBOnly(data, trackBeam, feeds)

    # collect total powers from each feed
    totals = {}
    for feed in feeds:
        print("finding total power for feed:", feed)
        # make this general for both a single pol, and averaging
        polPowers = []
        for pol in pols:
            # Ka has only one pol per feed
            if receiver == 'Rcvr26_40':
                feed = kaBeamMap[pol]
            freq = getFreqForData(data, feed, pol)
            # W-band and Argus have different total power equations
            if receiver == 'Rcvr68_92':
                channel = '%s%s' % (feed, pol)
                gain = gains[channel]
                totalPowerPol = calibrateTotalPowerRcvr68_92(data, feed, pol, freq, gain)
            else:
                totalPowerPol = calibrateTotalPower(data, feed, pol, freq)
            polPowers.append(totalPowerPol)
        totals[feed] = sum(polPowers) / float(len(pols))

    if mode == 'TotalPower' or len(feeds) < 2:
        return totals[feed]

    if mode == 'DualBeam':
        return calibrateDualBeam(totals, trackBeam, feeds)


def calibrateAll(projPath, scanNum):
    "Returns a dict of all the possible calibrated data products"

    dataMap = getDcrDataMap(projPath, scanNum)

    data = dataMap['data']
    trackBeam = dataMap['trackBeam']
    rcvr = dataMap['receiver']

    gains = None
    if rcvr == 'Rcvr68_92':
        gains = getRcvr68_92Gains(projPath, scanNum)

    print("**** data map summary for", rcvr)
    keys = sorted(data.keys())
    for k in keys:
        print(k, data[k][0][0], data[k][1])
    print("trackBeam: ", trackBeam)

    feeds = list(set([k[0] for k in data.keys()]))
    if trackBeam not in feeds:
        print("trackBeam not in Feeds!  Cant proces")
        return {}

    modes = getSupportedModes(data.keys(), receiver=rcvr)

    # TBF, Kluge: we still can't do Ka DualBeam or BeamSwitch
    if rcvr == 'Rcvr26_40':
        modes = ['Raw', 'TotalPower', 'BeamSwitchedTBOnly']

    pols = list(set([k[1] for k in data.keys()]))
    pols.append('Avg')

    # construct the options of mode and pols
    calTypes = []
    for mode in modes:
        for pol in pols:
            calTypes.append((mode, pol))

    cal = {}
    for mode, pol in calTypes:
        calData = calibrate(data, mode, pol, trackBeam, rcvr, gains=gains)
        key = (mode, getPolKey(pol))
        cal[key] = list(calData)

    return cal


def getRcvr68_92Gains(projPath, scanNum):
    "For this scan, calculate the gains from previous calseq scan"
    calSeqNum = findWBandCalSeqNum(projPath, scanNum)
    if calSeqNum != 0:
        cal = CalibrationResults()
        cal.makeCalScan(projPath, calSeqNum)
        calData = cal.calData
        print("calData: ", calData)
        scanInfo, gains, tsys = calData
    else:
        # NO CalSeq scan!  Just set all gains to 1.0
        gains = {}
        for pol in ['X', 'Y']:
            for feed in [1, 2]:
                channel = '%s%s' % (feed, pol)
                gains[channel] = 1.0
    return gains


def findWBandCalSeqNum(projPath, scanNum):
    "For the given project and scan, when is the most recent calseq?"
    scans = getScanProcedures(projPath)

    # find the most recent CALSEQ scan
    calseqName = "CALSEQ"
    calSeqScans = [scan for scan, procname in scans
                   if scan <= scanNum and procname == calseqName]
    # if we didn't find any, use 0 to mark this
    return calSeqScans[-1] if len(calSeqScans) > 0 else 0


def getScanProcedures(projPath):
    "Returns a list of each scan number and its procname"
    # projName = projPath.split('/')[-1]
    path = "/".join(projPath.split('/')[:-1])

    scanLog = fits.getdata(os.path.join(projPath, "ScanLog.fits"))
    scans = []
    for row in scanLog:
        _, scan, filepath = row
        if 'GO' in filepath:
            goFile = os.path.join(path, filepath)
            goHdu = fits.open(goFile)
            h = goHdu[0].header
            scans.append((scan, h['PROCNAME']))
    return scans


def calibrateTotalPowerRcvr68_92(data, feed, pol, freq, gain):
    "total power for W-band is just the off with a gain"
    offKey = (feed, pol, freq, 'Signal / No Cal')
    off, _ = data[offKey]
    # print("tp from: ", gain, keys, off[0])
    return gain * (off - np.median(off))


if __name__ == '__main__':

    # scanNum = 2
    # projPath = "/home/gbtdata/"
    # projPath = "/home/archive/science-data/12A"
    # proj = "AGBT16B_288_03"
    # proj = "AGBT12A_072_02"
    # proj = "AVLB17A_182_04"
    # fullpath = os.path.join(projPath, proj)

    #  /home/archive/science-data/16A/AGBT16A_085_04/ScanLog.fits
    # projectName = 'AGBT10A_005_04'
    projectName = 'AGBT16A_085_06'
    path = '/home/archive/science-data/16A'
    scanNum = 55
    projPath = os.path.join(path, projectName)
    # calseqScan = findWBandCalSeqNum(fullpath, scanNum)
    # print(calseqScan)
    r = calibrateAll(projPath, scanNum)
    print("calibrateAll:")
    for k, v in r.items():

        print(k, v[0])

    # import sys
    # projPath = sys.argv[1]
    # scanNum = int(sys.argv[2])
    # x = calibrateAll(projPath, scanNum)
    # print("result: ", x.keys())
