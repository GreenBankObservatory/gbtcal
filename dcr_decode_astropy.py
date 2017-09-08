from __future__ import print_function
import os
import sys
import traceback

import argparse
from astropy.io import fits
from astropy.table import Column, Table, join, hstack, vstack

import numpy as np
# import matplotlib.pyplot as plt

###
# Author: Thomas Chamberlin
# Date: 8/4/2017

# This script is in implementation of the techniques described in:
# https://safe.nrao.edu/wiki/bin/view/GB/Data/DCRDataDecoding
# and
# https://safe.nrao.edu/wiki/bin/view/GB/Software/SparrowDataProcessing
# Paul's script, 'dcrDecode.py', did all the hard work -- this is largely
# an effort to increase my understanding of the 'decoding' and 'calibration'
# processes. I also wanted to familiarize myself with the facilities
# in numpy and astropy for dealing with FITS files in a sensible manner.
###

# All valid receivers that use DCR data
RCVRS = [
    'RcvrPF_1',
    'RcvrPF_2',
    'RcvrArray1_2',
    'Rcvr1_2',
    'Rcvr2_3',
    'Rcvr4_6',
    'Rcvr8_10',
    'Rcvr12_18',
    'RcvrArray18_26',
    'Rcvr18_26',
    'Rcvr26_40',
    'Rcvr40_52',
    'Rcvr69_92',
    'RcvrArray75_115'
]


def eprint(string):
    """Given a string, prepend ERROR to it and print it to stderr"""

    print("ERROR: {}".format(string), file=sys.stderr)


def getFitsForScan(projPath, scanNum):
    """Given a project path and a scan number, return the a dict mapping
    manager name to the manager's FITS file (as an HDUList) for that scan"""

    # Try to open the scan log fits file
    scanLog = fits.getdata(os.path.join(projPath, "ScanLog.fits"))

    # Data for the given scan number
    scanInfo = scanLog[scanLog['SCAN'] == scanNum]
    managerFitsMap = {}
    for filePath in scanInfo['FILEPATH']:
        if "SCAN" not in filePath:
            _, _, manager, scanName = filePath.split("/")
            # we actually only care about these - no point in raising an error
            # if something like the GO FITS file can't be found.
            if manager in ['DCR', 'IF', 'Antenna'] or manager in RCVRS:
                fitsPath = os.path.join(projPath, manager, scanName)
                managerFitsMap[manager] = fits.open(fitsPath)

    return managerFitsMap


def getTableByName(hduList, tableName):
    """Given a FITS file HDU list and the name of a table, return its Astropy
    Table representation"""

    return Table.read(hduList[hduList.index_of(tableName)])


def getIfDataByBackend(ifHduList, backend='DCR'):
    """Given an IF FITS file, return a table containing only rows for
    the specified backend"""
    ifTable = getTableByName(ifHduList, 'IF')

    # First, we filter out all non-DCR backends
    # Create a 'mask' -- this is an array of booleans that
    # indicate which rows are associated with the DCR backend
    # NOTE: We need to strip whitespace from this column --
    # this is because our FITS files pad each charfield
    # https://github.com/astropy/astropy/issues/2608
    mask = np.char.rstrip(ifTable['BACKEND']) == backend
    # We then filter out these indices
    dcrData = ifTable[mask]
    return dcrData


def mapDcrDataToPort(dcrData, dcrPorts, dcrPortTable, calStates):
    """Given time-domain dcr data, return it instead as a mapping
    of port to all of the data that it trasmitted"""

    # Handle the port offset here. For every port in dcrPorts...
    for portIndex, port in enumerate([port + 1 for port in dcrPorts]):
        # ...for every state of the cal diode (on/off)...
        for calState in calStates:
            # ...create a row that maps a port and cal state to the
            # associated data
            #      PORT  CAL       DATA
            row = [port, calState, dcrData[..., portIndex, calState]]

            dcrPortTable.add_row(row)
    return dcrPortTable


def getAntennaTrackBeam(antHdu):
    """Given an Antenna FITS file, return which beam was the tracking beam"""

    return int(antHdu[0].header['TRCKBEAM'])


def consolidateFitsData(dcrHdu, ifHdu):
    """Given DCR and IF HDU objects, pull out the information needed
    to perform calibration into a single Astropy Table, then return it"""

    # STATE describes the phases in use
    dcrStateTable = getTableByName(dcrHdu, 'STATE')
    # RECEIVER describes which DCR ports
    dcrRcvrTable = getTableByName(dcrHdu, 'RECEIVER')
    # DATA contains the actual data recorded by the DCR
    dcrDataTable = getTableByName(dcrHdu, 'DATA')

    # How many unique CAL states are there?
    calStates = np.unique(dcrStateTable['CAL'])
    # There should be only 1 or 2 possible states
    if list(calStates) not in [[0], [1], [0, 1]]:
        raise ValueError("Invalid CAL states detected in DCR.RECEIVER.CAL: {}"
                         .format(calStates))

    # How many unique SIGREF states are there?
    sigRefStates = np.unique(dcrStateTable['SIGREF'])
    # There should be only 1 or 2 possible states
    if list(sigRefStates) not in [[0], [1], [0, 1]]:
        raise ValueError("Invalid SIGREF states detected in "
                         "DCR.RECEIVER.SIGREF: {}".format(sigRefStates))

    # DCR data from IF table
    ifDcrData = getIfDataByBackend(ifHdu)

    # Our port information is stored in the CHANNELID column of the
    # RECEIVER table
    # NOTE: These ports are 0-indexed, but in the IF FITS
    # file they are 1-indexed
    dcrPorts = dcrRcvrTable['CHANNELID']

    # Strip out unneeded/misleading columns
    filteredIfTable = ifDcrData[
        'RECEIVER', 'FEED', 'RECEPTOR', 'POLARIZE', 'CENTER_SKY',
        'BANDWDTH', 'PORT', 'SRFEED1', 'SRFEED2', 'HIGH_CAL'
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
    numPhasesPerPort = len(np.unique(dcrStateTable['SIGREF', 'CAL']))

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
                                    len(ifDcrData))
    except TypeError as e:
        eprint(traceback.format_exc(e))
        eprint("Could not stack DCR table. Is length of ifDcrData 0? {}"
              .format(len(ifDcrData)))
        eprint(ifDcrData)
        return None

    # We now have two tables, both the same length, and they can be simply
    # stacked together horizontally.
    filteredIfTable = hstack([filteredIfTable, expandedStateTable])

    # Okay! We now have a table that maps physical attributes to the different
    # states in which data was taken. That is, for each feed we have rows
    # that map it to the various SIGREF and CAL states that were active at
    # some point during the scan.
    # So, we now need to map these physical attributes to the actual data!

    # Get the sets of unique SIGREF and CAL states. Note that this could
    # _probably_ be done by simply grabbing the whole column from 
    # dcrStateTable, but this way we guarantee uniqueness.
    uniquePorts = np.unique(filteredIfTable['PORT'])
    uniqueSigRefStates = np.unique(filteredIfTable['SIGREF'])
    uniqueCalStates = np.unique(filteredIfTable['CAL'])

    phaseStateTable = dcrStateTable['SIGREF', 'CAL']
    phaseStateTable.add_column(Column(name='PHASE',
                                      data=np.arange(len(phaseStateTable))))

    # TODO: What is the proper way to find all combinations of these two lists?
    stuff = []

    # This is a reasonable assert to make, but it will fail when the IF FITS
    # only has a *subset* of the ports used by the DCR.  Sparrow ignores ports
    # NOT specified by the IF FITS file, wo we'll do the same
    #assert len(uniquePorts) == dcrDataTable['DATA'].shape[1]
    if len(uniquePorts) != dcrDataTable['DATA'].shape[1]:
        print("WARNING: IF ports are only a subset of DCR ports used")


    reshapedData = dcrDataTable['DATA'].reshape(len(dcrDataTable),
                                            len(uniquePorts),
                                            len(uniqueSigRefStates),
                                            len(uniqueCalStates))
    if len(uniquePorts) != reshapedData.shape[1]:
        eprint("Invalid shape? These should be equal: len(uniquePorts): {}; reshapedData.shape[1]: {}"
               .format(len(uniquePorts), reshapedData.shape[1]))

    # print("Reshaped from {} to {}".format(dcrDataTable['DATA'].shape,
                                          # reshapedData.shape))

    # TODO: I wonder if there is a way to avoid looping here altogether?
    for portIndex, port in enumerate([port + 1 for port in uniquePorts]):
        for sigRefState in uniqueSigRefStates:
            for calState in uniqueCalStates:
                phaseMask = (
                    (phaseStateTable['SIGREF'] == sigRefState) &
                    (phaseStateTable['CAL'] == calState)
                )
                # Assert that the mask doesn't match more than one row
                if np.count_nonzero(phaseMask) != 1:
                    raise ValueError("PHASE could not be unambiguously "
                                     "determined from given SIGREF ({}) "
                                     "and CAL ({})"
                                     .format(sigRefState, calState))
                phase = phaseStateTable[phaseMask]['PHASE'][0]
                dataForPortAndPhase = dcrDataTable['DATA'][..., portIndex, phase] 
                if not np.all(dataForPortAndPhase ==
                              reshapedData[..., portIndex, sigRefState, calState]):
                    eprint("Phase method data does not match reshape method data!")

                stuff.append(dcrDataTable['DATA'][..., portIndex, phase])

    filteredIfTable.add_column(Column(name='DATA', data=stuff))
    # TODO: Uncomment this if we are doing L band... something about
    # redundant data that needs to be removed
    # return filteredIfTable[filteredIfTable['PORT'] <= 3]
    return filteredIfTable


def getAntennaTemperature(calOnData, calOffData, tCal):
    countsPerKelvin = (np.sum((calOnData - calOffData) / tCal) /
                       len(calOnData))
    Ta = 0.5 * (calOnData + calOffData) / countsPerKelvin - 0.5 * tCal
    return Ta


def getHistogramArea(left, right, x, y):
    # Stolen from RcvrCalibration.py
    "Returns area under y from left to right along x as a histogram."

    assert x[0] < x[-1], \
           "Cannot retrieve sensible frequency information from DCR " + \
           "data. Check CENTER_SKY and/or BANDWDTH columns."

    assert left < right, \
           "The starting frequency must be less than the ending " + \
           "frequency in the DCR data."
    assert len(x) == len(y), \
           "DCR frequency and temperature data arrays are of unequal size."

    # Is range completely out of bounds?
    if right < x[0]:
        return (right - left) * y[0]
    if x[-1] < left:
        return (right - left) * y[-1]

    A = 0.0
    i = 1

    # Find the beginning.
    mid = (x[i] + x[i-1])/2.0
    while mid < left:
        i += 1
        mid = (x[i] + x[i-1])/2.0

    # Add part or extension area of the the first histogram
    A = (mid - left) * y[i - 1]
    i += 1

    # Add up the whole areas of the middle histograms
    while i < len(x):
        new_mid = (x[i] + x[i-1])/2.0
        if new_mid > right:
            break
        A += (new_mid - mid) * y[i-1]
        mid = new_mid
        i += 1

    # Add part or extension area of the the last histogram
    A += (right - mid) * y[i-1]

    return A


def getTcal(rcvrCalTable, feed, receptor, polarization, highCal,
            centerSkyFreq, bandwidth):
    """Given a table of receiver calibration data and the parameters
    by which to calibrate, return a Tcal value"""

    # find freq. range for tcal!
    # TODO: What is this? Where did it come from?
    freqStart = centerSkyFreq - bandwidth / 2.0
    freqEnd = centerSkyFreq + bandwidth / 2.0

    mask = (
        (rcvrCalTable['FEED'] == feed) &
        (np.char.rstrip(rcvrCalTable['RECEPTOR']) == receptor) &
        (np.char.rstrip(rcvrCalTable['POLARIZE']) == polarization)
    )
    maskedTable = rcvrCalTable[mask]
    highCalTemps = maskedTable['HIGH_CAL_TEMP']
    lowCalTemps = maskedTable['LOW_CAL_TEMP']
    # TODO: Shouldn't this be based off of the highCal arg? -- DONE
    # TODO: Sometimes there are values in both columns... what then?? -- DONE
    calTemps = highCalTemps if highCal else lowCalTemps
    frequencies = maskedTable['FREQUENCY']

    area = getHistogramArea(freqStart, freqEnd, frequencies, calTemps)

    return area / abs(freqEnd - freqStart)


def calibrateTotalPower(calOnData, calOffData, feed, receptor, polarization,
                        centerSkyFreq, bandwidth, highCal, rcvrCalTable):
    tCal = getTcal(rcvrCalTable, feed, receptor, polarization,
                   highCal, centerSkyFreq, bandwidth)

    power = getAntennaTemperature(calOnData, calOffData, tCal)

    return power


def calibrateMultiFeed(dataTable, polarization, rcvrCalTable, trackBeam=None):
    """Given a data table (which supplies all required data) and a
    polarization to calibrate for, return the calibrated data"""

    # We calibrate by feed, so let's iterate through all of those
    # mapFeedToData maps a feed to its associated calibrated data
    mapFeedToData = {}
    for feed in np.unique(dataTable['FEED']):
        mask = ((dataTable['FEED'] == feed) &
                (np.char.rstrip(dataTable['POLARIZE']) == polarization))
        maskedData = dataTable[mask]

        assert len(np.unique(maskedData['FEED', 'POLARIZE'])) == 1, \
            "There should be exactly ONE unique combination of given " \
            "feed, receptor, and polarization in the table"
        assert len(np.unique(maskedData['RECEPTOR'])) == 1, \
            "ERROR: >1 RECEPTOR in maskedData: {}".format(maskedData)
        assert len(np.unique(maskedData['CENTER_SKY'])) == 1, \
            "ERROR: >1 CENTER_SKY in maskedData: {}".format(maskedData)
        assert len(np.unique(maskedData['BANDWDTH'])) == 1, \
            "ERROR: >1 BANDWDTH in maskedData: {}".format(maskedData)
        assert len(np.unique(maskedData['HIGH_CAL'])) == 1, \
            "ERROR: >1 HIGH_CAL in maskedData: {}".format(maskedData)

        receptor = np.char.rstrip(maskedData['RECEPTOR'])[0]
        centerSkyFreq = maskedData['CENTER_SKY'][0]
        bandwidth = maskedData['BANDWDTH'][0]
        highCal = maskedData['HIGH_CAL'][0]

        calOnMask = maskedData['CAL'] == 1
        calOffMask = maskedData['CAL'] == 0

        # we can't calibrate nothing if we have only one phase,
        # at least for typical receivers
        calValues = len(np.unique(maskedData['CAL']))
        if calValues < 2:
            print("Not enough phases, not calibrating!")
            return None

        calOnData = maskedData[calOnMask]['DATA'].flatten()
        calOffData = maskedData[calOffMask]['DATA'].flatten()

        power = calibrateTotalPower(
            calOnData, calOffData, feed, receptor, polarization,
            centerSkyFreq, bandwidth, highCal, rcvrCalTable
        )

        mapFeedToData[feed] = power

    assert len(np.unique(dataTable['SRFEED1'])) == 1
    assert len(np.unique(dataTable['SRFEED2'])) == 1

    numFeeds = len(np.unique(dataTable['FEED']))
    assert numFeeds == len(mapFeedToData)
    if numFeeds == 1:
        # If we only have one feed, then we don't do any beam subtraction;
        # we simply return the data
        return mapFeedToData.values()[0]
    elif numFeeds == 2:
        # If we have two feeds, then we subtract the reference beam
        # from the signal beam, then return the result
        # TODO: derive this from TRCKBEAM? Or does this already work?
        # TODO: I would have thought these would map the other way around...
        refFeed = dataTable['SRFEED1'][0]
        sigFeed = dataTable['SRFEED2'][0]

        # the beam difference depends on which is the tracking beam
        # print("trackBeam: ", trackBeam, type(trackBeam), sigFeed, type(sigFeed))
        if trackBeam is None:
            # well, crap, just choose one
            sig = sigFeed
            ref = refFeed
        else:
            if sigFeed == trackBeam:
                sig = sigFeed
                ref = refFeed
            else:
                sig = refFeed
                ref = sigFeed
        # return mapFeedToData[sigFeed] - mapFeedToData[refFeed]
        return mapFeedToData[sig] - mapFeedToData[ref]
    else:
        raise TypeError("Receivers with >2 feeds are not "
                        "supported (got: {} feeds)".format(numFeeds))


def calibrateDcrData(dcrDataTable, beam, polarization, rcvrCalTable):
    """Given the data to calibrate, the beam and polarization to calibrate
    for, and a table containing receiver calibration data, calibrate the data
    and return the result"""

    # print("Columns:")
    # print(dcrDataTable.columns)
    # print("Attributes:")
    # for column in ['FEED', 'POLARIZE', 'CENTER_SKY', 'CAL', 'RECEIVER']:
    #     print("{}: {}".format(column, np.unique(dcrDataTable[column].data)))

    # The data table should contain only one receiver, frequency, and bandwidth
    assert len(np.unique(dcrDataTable['RECEIVER'])) == 1
    assert len(np.unique(dcrDataTable['CENTER_SKY'])) == 1
    assert len(np.unique(dcrDataTable['BANDWDTH'])) == 1

    power = calibrateMultiFeed(dcrDataTable, polarization, rcvrCalTable)

    return power


def getRcvrCalTable(rcvrCalHduList):
    """Given a receiver calibration FITS file, combine the relevant
    data and return it"""

    # TODO: This causes metadata conflicts, but I don't think it matters --
    # just ignore the warnings??
    table = None
    for rcvrCalHdu in rcvrCalHduList[1:]:
        # Make sure that the HDU is the proper type
        # TODO: Is this a valid assumption?
        if rcvrCalHdu.header['EXTNAME'] == "RX_CAL_INFO":
            tmpTable = Table.read(rcvrCalHdu)

            # Pull these values from the header and expand them to fill
            # an entire column
            for key in ['FEED', 'RECEPTOR', 'POLARIZE']:
                column = Column(name=key,
                                data=[tmpTable.meta[key]] * len(tmpTable))
                tmpTable.add_column(column)

            # Delete all the meta data; we don't need it
            for key in tmpTable.meta:
                del tmpTable.meta[key]

            # Stack the table on top of the new one
            if table:
                # Use exact here to catch any weird errors -- mismatched
                # columns, etc.
                table = vstack([table, tmpTable], join_type='exact')
            else:
                table = tmpTable

    return table


def parseArgs():
    """Parse CLI arguments and return them"""

    parser = argparse.ArgumentParser()
    parser.add_argument("projPath",
                        help="The path to the project directory")
    parser.add_argument("scanNum",
                        help="The scan number you wish to process",
                        type=int)
    # TODO: Can we derive receiver in all cases?
    parser.add_argument("receiver",
                        help="The name of the receiver")
    # TODO: Support BOTH
    parser.add_argument("polarization",
                        help="The polarization to calibrate for",
                        choices=['X', 'Y', 'L', 'R'])

    return parser.parse_args()


def processDcrData(projPath, scanNum, receiver, polarization):
    # A mapping of Manager -> FITS file for given scan
    fitsForScan = getFitsForScan(projPath, scanNum)
    # if receiver not in fitsForScan.keys():
    #     raise ValueError("Given receiver '{}' took no data during scan {}!"
    #                      .format(receiver, scanNum))
    scanName = os.path.basename(fitsForScan['IF'].filename())
    # print("Scan Name: {}".format(scanName))

    result = consolidateFitsData(fitsForScan['DCR'], fitsForScan['IF'])
    # print("-" * 80)
    # print("FINAL RESULT:")
    # print(result)
    # print("-" * 80)
    return result
    
    rcvrCalHduList = fitsForScan[receiver]
    rcvrCalTable = getRcvrCalTable(rcvrCalHduList)

    # TODO: This isn't used right now...
    beam = getAntennaTrackBeam(fitsForScan['Antenna'])


    # test(projPath, scanName, receiver,
    #      os.path.basename(fitsForScan[receiver].filename()), result)

    # power = calibrateDcrData(result, beam, polarization, rcvrCalTable)
    # paulDcrDecode.plotData(power, scanName, receiver,
    #                        projPath, polarization)

def calibrateDefaultDcrData(projPath, scanNum, receiver, polarization):
    "Returns the default (total power, or dual beam) calibration"
    fitsForScan = getFitsForScan(projPath, scanNum)
    result = consolidateFitsData(fitsForScan['DCR'], fitsForScan['IF'])
    rcvrCalHduList = fitsForScan[receiver]
    rcvrCalTable = getRcvrCalTable(rcvrCalHduList)
    trackBeam = getAntennaTrackBeam(fitsForScan['Antenna'])
    power = calibrateMultiFeed(result, polarization, rcvrCalTable, trackBeam=trackBeam)
    return power


def calibrateDefaultDcrPolarizations(projPath, scanNum, receiver):
    "Returns the default (total power, or dual beam) calib. for all pols"

    # decode the dcr data first
    fitsForScan = getFitsForScan(projPath, scanNum)
    data = consolidateFitsData(fitsForScan['DCR'], fitsForScan['IF'])

    # now construct a dict of calibrated results using the same keys
    # that we constructed for the sparrow data
    pols = [p.strip() for p in list(set(list(data['POLARIZE'])))]
    dataMap = {}
    polMap = {
        'X': 'XL',
        'L': 'XL',
        'Y': 'YR',
        'R': 'YR',
    }
    numFeeds = len(np.unique(data['FEED']))
    mode = 'TotalPower' if numFeeds == 1 else 'DualBeam'
    # calibrate each of the polarizations
    for pol in pols:
        polKey = polMap[pol]

        power = calibrateDefaultDcrData(projPath,
                                        scanNum,
                                        receiver,
                                        pol)
        if power is not None:
            dataMap[(mode, polKey)] = power

    # then calibrate the average
    if len(pols) > 1:
        pol1 = (mode, polMap[pols[0]])
        pol2 = (mode, polMap[pols[1]])
        if pol1 in dataMap and pol2 in dataMap:
            dataMap[(mode, 'Avg')] = (dataMap[pol1] + dataMap[pol2]) / 2.0

    # for k, v in dataMap.items():
        # print(k, v[0])

    return dataMap


if __name__ == '__main__':
    args = parseArgs()
    projPath = vars(args)['projPath']
    scanNum = vars(args)['scanNum']
    receiver = vars(args)['receiver']
    # Call processDcrData with all CLI args
    calibrateDefaultDcrPolarizations(projPath, scanNum, receiver)
