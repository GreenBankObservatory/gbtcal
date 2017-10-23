import os

from astropy.io import fits
from astropy.table import Column, Table, vstack

import numpy

from gbtcal.dcrtable import DcrTable
from gbtcal.table.stripped_table import StrippedTable

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
# TODO: This should be derived from an external table
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
    'Rcvr68_92',
    'RcvrArray75_115'
]


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
                try:
                    managerFitsMap[manager] = fits.open(fitsPath)
                except IOError:
                    # TODO: logger
                    print("{} is listed in ScanLog.fits as having data for "
                          "scan {}, but no such data exists in {}! Skipping."
                          .format(manager, scanName, fitsPath))

    return managerFitsMap


def getAntennaTrackBeam(antHdu):
    """Given an Antenna FITS file, return which beam was the tracking beam"""

    return int(antHdu[0].header['TRCKBEAM'])


def getAntennaTemperature(calOnData, calOffData, tCal):
    countsPerKelvin = (numpy.sum((calOnData - calOffData) / tCal) /
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
    mid = (x[i] + x[i - 1]) / 2.0
    while mid < left:
        i += 1
        mid = (x[i] + x[i - 1]) / 2.0

    # Add part or extension area of the the first histogram
    A = (mid - left) * y[i - 1]
    i += 1

    # Add up the whole areas of the middle histograms
    while i < len(x):
        new_mid = (x[i] + x[i - 1]) / 2.0
        if new_mid > right:
            break
        A += (new_mid - mid) * y[i - 1]
        mid = new_mid
        i += 1

    # Add part or extension area of the the last histogram
    A += (right - mid) * y[i - 1]

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
        (rcvrCalTable['RECEPTOR'] == receptor) &
        (rcvrCalTable['POLARIZE'] == polarization)
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
            tmpTable = StrippedTable.read(rcvrCalHdu)

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


def sigCalStateToPhaseName(sigRefState, calState):
    "Map sigref and cal indicies in data to a GFM-style phase name"
    name1 = "Signal" if sigRefState == 0 else "Reference"
    name2 = "Cal" if calState == 1 else "No Cal"
    return "%s / %s" % (name1, name2)


# TODO: This should be removed
def getDcrDataDescriptors(data):
    "Returns description as a list of (feed, pol, freq, phase)"
    columns = ['FEED', 'POLARIZE', 'CENTER_SKY', 'SIGREF', 'CAL']
    desc = data[columns]

    # convert this astropy table to a simple list
    descriptors = [d.as_void() for d in list(desc)]

    # finally, do a little formatting and translation
    ds = []
    for feed, pol, freq, sigref, cal in descriptors:
        pol = pol.strip()
        phase = sigCalStateToPhaseName(sigref, cal)
        ds.append((feed, pol, freq, phase))
    return ds


def decode(projPath, scanNum):
    """
    Given a project path and a scan number, return the "decoded"
    data as a DcrTable instance.
    """
    fitsForScan = getFitsForScan(projPath, scanNum)
    table = DcrTable.read(fitsForScan['DCR'], fitsForScan['IF'])
    table.meta['TRCKBEAM'] = getAntennaTrackBeam(fitsForScan['Antenna'])
    return table
