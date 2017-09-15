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

# from   gbt.dcr.DCR         import DCR
# from   gbt.ccb.CCB         import CCB
# from   gbt.spectrometer    import SpectrometerBanks
# from   gbt.vegas           import VegasBanks
# from   gbt.receiver        import RcvrCalibration
#from   gbt.receiver        import Rcvr68_92
# from   gbt.ygor            import getConfigValue


from ConfigParser import ConfigParser

from Rcvr68_92 import Rcvr68_92
from dcr_decode_astropy import getFitsForScan, consolidateFitsData
from dcr_decode_astropy import getDcrDataDescriptors

import numpy


class Backend:

    def __init__(self, data, dcrHdu):
        self.dcrHdu = dcrHdu
        self.data = data
        self.descriptors = getDcrDataDescriptors(data)

        feedPolCombos = list(set([(f, p) for f, p, _, _ in self.descriptors]))
        self.channels = ["%s%s" % (f, p) for f, p in feedPolCombos]

        self.name = "DCR"


    def GetRawPower(self, feed, pol, phase):

        sigref, cal = phase

        mask = ((self.data['FEED'] == feed) &
                (numpy.char.rstrip(self.data['POLARIZE']) == pol) &
                (self.data['SIGREF'] == sigref) &
                (self.data['CAL'] == cal))

        return self.data[mask]['DATA'][0]

    def GetIntegrationTime(self):

        h = self.dcrHdu[0].header
        return h['DURATION']

    def GetIntegrationStartTimes(self):

        dataTab = self.dcrHdu[3].data
        return dataTab.field('TIMETAG')

    def GetNumSamplers(self):

        pols = numpy.unique(self.data['POLARIZE'])
        feeds = numpy.unique(self.data['FEED'])
        freqs = numpy.unique(self.data['CENTER_SKY'])

        return len(pols) * len(feeds) * len(freqs)

    def GetPhases(self):
        phases = numpy.unique(self.data[['SIGREF', 'CAL']])
        return phases

    def GetNumPhases(self):

        return len(self.GetPhases())


class CalSeqScan:

    def __init__(self, projectPath, scanNum):
        # self.project = project
        # self.scan    = scan
        self.projectPath = projectPath
        self.scanNum = scanNum

        self.fitsMap = getFitsForScan(projectPath, scanNum)

        print("fits files", self.fitsMap.keys())
        self.channels = []
        self.ports = []  # need ordered list to correspond with data columns
        self.SetBackend()
        self.SetReceiver()
        self.InitData()

    def SetBackend(self):

        dcrHdu = self.fitsMap['DCR']
        ifHdu = self.fitsMap['IF']
        data = consolidateFitsData(dcrHdu, ifHdu)

        self.backend = Backend(data, dcrHdu)

        # if self.scan.HasDevice('DCR'):
            # self.backend = DCR(self.GetDataConnection())
        # elif self.scan.HasDevice('Spectrometer'):
        #     self.backend = SpectrometerBanks(self.scan, self.GetReceiverCal())
        # elif self.scan.HasDevice('VEGAS'):
        #     self.backend = VegasBanks(self.scan, self.GetReceiverCal())
        # else:
            # raise "Only supporting DCR"

    def getBackendName(self):
        return self.backend.name

    # def GetDataConnection(self):
        # return self.scan.getDataConnection()

    def GetReceiverCal(self):
        rcvrName = self.scan.getRcvrName()
        try:
            if self.project is not None and self.project.hasReceiver(rcvrName):
                return self.project.getRcvrCalibration(rcvrName)
            else:
                return RcvrCalibration(scan.getDataConnection())
        except:
            return None

    def SetReceiver(self):
        hdu = self.fitsMap['Rcvr68_92']
        self.receiver = Rcvr68_92(hdu, debug=True)

    def InitData(self):
        self.scanData = {}

    def getTwarm(self):
        """ Uses receiver class to get TWARM from receiver FITS file """
        if self.receiver:
            # TBF: for auto scan returns header value of twarm unless have dmjd arg
            return self.receiver.getTwarm()
        return 0

    def getTcold(self):
        """ Reads TCOLD from CalSeq.conf config file """
        ygorTelescope = "/home/sim" #getConfigValue("/home/sim", "YGOR_TELESCOPE")
        filename = ygorTelescope + "/etc/config/CalSeq.conf"
        cp = ConfigParser()
        cp.read(filename)
        try:
            return float(cp.get("all_modes", "tcold"))
        except:
            return 50.0  #default

    def getCalPos(self):
        return self.receiver.getCalpos()

    def isAuto(self):
        return self.receiver.isAuto()

    def getScanData(self):
        """ self.scanData is a dict of format {channel: (type, Raw Power data)}
            where:
            channel = 1X, 1Y, 2X, or 2Y
            type    = Vwarm, Vcold, Observing, Position2, or Position5
        """
        return self.scanData

    def getChannels(self):
        return self.channels

    def processCalseqScan(self):
        """ Read channel data and put in scanData dictionary
            with calibration wheel position metadata """

        if self.getBackendName() == "DCR":
            print "processCalseqScan for DCR"
            # Get DCR FITS DATA 'TIMETAG' column
            # (we only need this for auto mode,
            # but don't want to repeat this in loop)
            dmjds = self.backend.GetIntegrationStartTimes()

            # for s in range(self.backend.GetNumSamplers()):
            #     for p in range(self.backend.GetNumPhases()):
            #         # Which dict to use?
            #         feed = self.backend.getSampler(s).GetFeed()
            #         pol  = self.backend.getSampler(s).GetPolarization()
            #         channel = str(feed) + pol
            for channel in self.backend.channels:
                for phase in self.backend.GetPhases():
                    print "channel, phase: ", channel, phase
                    self.channels.append(channel)
                    feed = int(channel[0])
                    pol = channel[1]
                    # get the data for that channel
                    channelData = self.backend.GetRawPower(feed, pol, phase)

                    print("data", channelData)

                    if self.isAuto():  # auto CalSeq
                        print "Auto calseq!"
                        # This is the more complicated case;
                        # Have to parse channelData according to calpos
                        autoData = {}
                        tint = self.backend.GetIntegrationTime()
                        for idx, dmjd in enumerate(dmjds):
                            calPosition = self.receiver.getPosition(dmjd, tint)
                            if calPosition != "Unknown":
                                dataType = self.getDataType(calPosition, feed)
                                try:
                                    autoData[dataType].append(channelData[idx])
                                except KeyError:
                                    # start a list for this dataType
                                    autoData[dataType] = [channelData[idx]]
                        for datatype in autoData.keys():
                            try:
                                self.scanData[channel].append((datatype,\
                                               numpy.array(autoData[datatype])))
                            except KeyError:
                                self.scanData[channel] = [(datatype,\
                                               numpy.array(autoData[datatype]))]
                    else:  # manual CalSeq
                        # This is the simple case, all data is the same type
                        calPosition = self.getCalPos()
                        dataType = self.getDataType(calPosition, feed)
                        # Now put data in dict
                        self.scanData[channel] = (dataType, channelData)
                    print "CalSeqScan.scanData: ", self.scanData    
        elif self.getBackendName() in ["Spectrometer", "Vegas"]:
            phase = 0 

            for beam in self.backend.getBeams():
                for pol in self.backend.getPolarizations():
                    channel = str(beam) + pol[0]
                    self.channels.append(channel)
                    channelData = None
                    if self.isAuto(): #auto CalSeq
                        autoData = {}
                        for ifnum in self.backend.getIFNumbers():
                            # retrieve the needed Spectrometer class
                            bankIdx = self.backend.getBankIndex(beam, pol, ifnum)
                            bank = self.backend.getBank(bankIdx)

                            # get data for stationary wheel positions during scan
                            tint = bank.GetIntegrationTime()
                            dmjds = bank.GetIntegrationStartTimes()
                            for idx, dmjd in enumerate(dmjds):
                                calPosition = self.receiver.getPosition(dmjd, tint)
                                if calPosition != "Unknown":
                                    dataType = self.getDataType(calPosition, beam)
                                    newData = self.backend.getRawPowerByValues(beam, pol, ifnum, idx, phase)
                                    if numpy.isnan(newData).any():
                                        continue
                                    try:
                                        autoData[dataType] = numpy.concatenate((autoData[dataType], newData))
                                    except KeyError:
                                        autoData[dataType] = newData
                        for datatype in autoData.keys():
                            try:
                                self.scanData[channel].append((datatype, autoData[datatype]))
                            except KeyError:
                                self.scanData[channel] = [(datatype, autoData[datatype])]
                    else:  # manual CalSeq
                        for ifnum in self.backend.getIFNumbers():
                            for integ in range(self.backend.getNumIntegrations()):
                                newData = self.backend.getRawPowerByValues(beam, pol, ifnum, integ, phase)
                                try:
                                    channelData = numpy.concatenate((channelData, newData))
                                except ValueError:
                                    channelData = newData

                        calPosition = self.getCalPos()
                        dataType = self.getDataType(calPosition, beam)
                        self.scanData[channel] = (dataType, channelData)

    def getDataType(self, calPos, feed):
        """ Converts cal position Cold1/2 to Vwarm or Vcold depending on feed """
        if "Cold" in calPos:
            # Convert calPos to key 'Vwarm' or 'Vcold'
            beamLoad = { "Cold1"    : ("Vcold", "Vwarm"),
                         "Cold2"    : ("Vwarm", "Vcold")}
            dataType = beamLoad[calPos][feed - 1]
        else:
            dataType = calPos
        return dataType


if __name__ == "__main__":
    projPath = "/home/gbtdata/AGBT16B_288_03"
    scanNum = 1
    scan = CalSeqScan(projPath, scanNum)
    print("scan: ", scan)
    scan.processCalseqScan()
