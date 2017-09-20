# Copyright (C) 2014 Associated Universities, Inc. Washington DC, USA.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 675 Mass Ave Cambridge, MA 02139, USA.
#
# Correspondence concerning GBT software should be addressed as follows:
#     GBT Operations
#     National Radio Astronomy Observatory
#     P. O. Box 2
#     Green Bank, WV 24944-0002 USA

import os
import numpy

from CalSeqScan import CalSeqScan
# from   gbt.ygor import getConfigValue
from astropy.io import fits


class CalibrationResults:
    """ Provides scan processing support for a set of calibration scans """

    def __init__(self):
        self.InitObservation()

    def InitObservation(self):
        """ make a clean slate for a new set of calibration scans """
        self.calibrated = False
        self.firstscan = None
        self.backend = None
        self.Twarm = None
        self.Tcold = None
        self.scans = {}      # CalSeqScan objects for scans in set
        self.gain = {}       # scalar gain
        self.gain_data = {}  # array gain
        self.Tsys = {}       # scalar Tsys
        self.Tsys_data = {}  # array Tsys
        self.calData = ()    # scan metadata and gain/Tsys data in tuple

###### Getters: ######
    def getFirstScan(self):
        """ Returns first scan number in calibration scan sequence """
        return self.firstscan

    def getScannums(self):
        """ Returns list of scan numbers in the calibration sequence set """
        return self.scannums

    def getBackend(self):
        """ Returns backend used in calibration scan sequence """
        return self.backend

    def getTwarm(self):
        """ Returns averaged Twarm for COLD1 and COLD2 scans """
        return self.Twarm

    def getTcold(self):
        """ Returns averaged Tcold for COLD1 and COLD2 scans """
        return self.Tcold

    def getGain(self):
        """ Returns gain dictionary:
            key:    channel name, e.g. '1X', '2Y'
            value:  gain (scalar; median value of gain array) """
        return self.gain

    def getGainData(self):
        """ Returns gain dictionary:
            key:    channel name, e.g. '1X', '2Y'
            value:  gain array """
        return self.gain_data

    def getTsys(self):
        """ Returns Tsys dictionary:
            key:   channel name + sky observing position, e.g. '1X, Observing'
            value: Tsys (scalar; median value of Tsys array """
        return self.Tsys

    def getTsysData(self):
        """ Returns Tsys dictionary:
            key:   channel name + sky observing position, e.g. '1X, Observing'
            value: Tsys array """
        return self.Tsys_data

    def getCalData(self):
        """ Get scan metadata, gain dict, and tsys dict in tuple form """
        return self.calData

    def isComplete(self):
        """ Returns bool to indicate if processing is complete """
        return self.calibrated

##########################


    def getScanIndexOfObservation(self, projPath, scanNum):

        go = self.getGOFits(projPath, scanNum)
        h = go[0].header
        return h['PROCSEQN'], h['PROCSIZE']

    def getGOFits(self, projPath, scanNum):

        # Try to open the scan log fits file
        scanLog = fits.getdata(os.path.join(projPath, "ScanLog.fits"))

        # Data for the given scan number
        scanInfo = scanLog[scanLog['SCAN'] == scanNum]
        for filePath in scanInfo['FILEPATH']:
            if "SCAN" not in filePath:
                _, _, manager, scanName = filePath.split("/")

                # we actually only care about these - no point in raising an error
                # if something like the GO FITS file can't be found.
                if manager == "GO":
                    fitsPath = os.path.join(projPath, manager, scanName)

        if fitsPath:
            return fits.open(fitsPath)
        else:
            return None

    def makeCalScan(self, projPath, scanNum):
        """Create CalSeqScan objects to process this scan"""

        # projectName = project.GetName()
        projectName = projPath.split('/')[-1]

        # Find scan nums that *should be* in this calibration sequence
        # and init data if this is a new sequence
        thisScannum = scanNum  # scan.getScanNumber()
        # procseqn, procsize = scan.getScanIndexOfObservation()
        procseqn, procsize = self.getScanIndexOfObservation(projPath, scanNum)

        self.scannums = self.determineScans(thisScannum, procseqn, procsize)
        if self.scannums[0] != self.firstscan:
            self.InitObservation()
            self.firstscan = self.scannums[0]

        # Make CalSeqScan object for this scan and add to scans dictionary
        self.scans[thisScannum] = CalSeqScan(projPath, scanNum)
        self.backend = self.scans[thisScannum].getBackendName()
        haveAllScans = self.makeCalObservation(projPath, procsize)
        if haveAllScans:
            print "haveAllScans!"
            self.calcGainTsys()
            self.saveData(projectName, self.backend, self.getGain(), self.getTsys())
        else:
            print "Incomplete calibration sequence"

    def makeCalObservation(self, project, procsize):
        """
        Make dict of CalSeqScans for scannums
        {scannum: CalSeqScan}
        """
        # Try to complete the set
        if len(self.scans) != len(self.scannums):
            for scannum in self.scannums:
                if scannum not in self.scans.keys():
                    scanProcseqn = self.scannums.index(scannum) + 1
                    self.addScan(scannum, project, scanProcseqn, procsize)

        # Check for complete set
        # print "Scan numbers in calibration sequence:", sorted(self.scans.keys())
        return len(self.scans) == len(self.scannums)

    def determineScans(self, scannum, procseqn, procsize):
        """Determine which scans are part of this calibration"""
        firstscan = scannum - procseqn + 1
        lastscan = firstscan + procsize - 1
        return range(firstscan, lastscan + 1)

    def addScan(self, scannum, project, seqn, size):
        """Adds CalSeqScan to self.scans for given scan number"""
        try:
            idx = project.getScanIndexByNumber(scannum)
            scan = project.getScan(idx)
        except Exception:
            # If observing all scans not available yet...
            return
        # We've got the scan, but is it part of the sequence?
        if self.checkScan(scan, seqn, size):
            self.scans[scannum] = CalSeqScan(project, scan)

    def checkScan(self, scan, expectedSeqn, expectedSize):
        """Does this scan fit into sequence correctly?"""
        scanOkay = True
        # Check PROCSCAN
        if not scan.isCalSeqScan(): scanOkay = False
        # Check PROCSEQN and PROCSIZE
        seqn, size = scan.getScanIndexOfObservation()
        if (seqn != expectedSeqn) or (size != expectedSize):  scanOkay = False
        return scanOkay

    def getCalSeqData(self):
        """
        Assemble calseq data into dict by channel, i.e.:
            {
                channel: {
                    "Observing": [data],
                    "Vcold": [data],
                    "Vwarm": [data]
                }
            }
        """
        twarm = []
        tcold = []
        scanData = {}
        calSeqData = {}

        for scannum in self.scans.iterkeys():
            print "getCAlSeqData for scannum", scannum

            calSeqScan = self.scans[scannum]

            # Process scan data into dictionary:
            # sky, Vwarm, and/or Vcold data for this scan for each channel
            calSeqScan.processCalseqScan()
            scanData = calSeqScan.getScanData()

            # get Twarm and Tcold data for Cold1 and Cold2 scans
            if "Cold" in calSeqScan.getCalPos():
                twarm.append(numpy.float64(calSeqScan.getTwarm()))
                tcold.append(numpy.float64(calSeqScan.getTcold()))
           
            # assemble channel scan data for all CalSeq scans in one dictionary
            for channel in calSeqScan.getChannels():
                if isinstance(scanData[channel], list):
                    # auto mode makes list with all channel data in it (in one scan);
                    calSeqData[channel] = scanData[channel]
                else:
                    # manual mode makes tuple for each channel for each scan
                    # so put in list
                    try:
                        calSeqData[channel].append(scanData[channel])
                    except KeyError:
                        calSeqData[channel] = [scanData[channel]]

        self.Twarm = numpy.mean(twarm)
        self.Tcold = numpy.mean(tcold)
        return calSeqData

    def calcGainTsys(self):
        """
        Find gain & Tsys for each channel.
        Save in self.gain and self.Tsys dicts
        """
        calSeqData = self.getCalSeqData()
        
        for channel in calSeqData.keys():
            channelData = {}
            for data in calSeqData[channel]:
                channelData[data[0]] = data[1]

            # Calculate gain
            twarm = self.getTwarm()
            tcold = self.getTcold()
            try:
                vwarm = numpy.median(channelData['Vwarm'])
                vcold = numpy.median(channelData['Vcold'])
                gain_array = (twarm - tcold) / (vwarm - vcold)
            except KeyError:
                print "Missing Vwarm or Vcold data for channel", channel, ": setting gain to 1.0"
                gain_array = 1.0
            self.gain_data[channel] = gain_array
            self.gain[channel] = numpy.median(gain_array)

            for sky in ["Observing", "Position2", "Position5"]:
                try:
                    Tsys_array = self.gain[channel] * channelData[sky]
                    tsys_key = channel + "," + sky
                    self.Tsys_data[tsys_key] = Tsys_array
                    self.Tsys[tsys_key] = numpy.median(Tsys_array)
                except KeyError:
                    if sky == "Observing":
                        print "Missing Observing (Sky) data for channel", channel, ": cannot calculate Tsys"
                    pass
        self.calibrated = True

    def saveData(self, projectName, backend, gains, Tsys):   
        """
        Save this data in dict for retrieval from GFM.
        Also save data in text file for AutoOOF processing.
        """

        scanInfo = {}
        scanInfo['project'] = projectName
        scanInfo['backend'] = backend
        scanInfo['scans'] = self.getScannums()
        self.calData = (scanInfo, gains, Tsys)
        self.saveTextFile(self.calData)

    def saveTextFile(self, data):
        """
        Save calibration data in text file for access from other processing.
        """

        # ygorTel = getConfigValue('/home/gbt', 'YGOR_TELESCOPE')
        ygorTel = '/home/sim/'
        path = ygorTel + "/etc/log/calibration/calseqdata.txt"
        # add keys for gain and tsys for easier readout
        data[0]['gain'] = data[1]
        data[0]['tsys'] = data[2]
        datafile = open(path, 'w')
        datafile.write(str(data[0]))
        datafile.close()

if __name__ == "__main__":
    projPath = "/home/gbtdata/AGBT16B_288_03"
    scanNum = 1
    cal = CalibrationResults()
    cal.makeCalScan(projPath, scanNum)
