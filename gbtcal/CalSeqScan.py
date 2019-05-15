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

import logging

import numpy
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser

from .Rcvr68_92 import Rcvr68_92
from gbtcal.decode import getFitsForScan, getDcrDataDescriptors
from gbtcal.dcrtable import DcrTable


logger = logging.getLogger(__name__)


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

        logger.debug("fits files %s", list(self.fitsMap.keys()))
        self.channels = []
        self.ports = []  # need ordered list to correspond with data columns
        self.SetBackend()
        self.SetReceiver()
        self.InitData()

    def SetBackend(self):

        dcrHdu = self.fitsMap['DCR']
        ifHdu = self.fitsMap['IF']
        data = DcrTable.read(dcrHdu, ifHdu)

        self.backend = Backend(data, dcrHdu)

    def getBackendName(self):
        return self.backend.name

    # def GetDataConnection(self):
        # return self.scan.getDataConnection()

    def GetReceiverCal(self):
        rcvrName = self.scan.getRcvrName()
        try:
            return self.project.getRcvrCalibration(rcvrName)
        except Exception:
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
        ygorTelescope = "/home/sim"  # getConfigValue("/home/sim", "YGOR_TELESCOPE")
        filename = ygorTelescope + "/etc/config/CalSeq.conf"
        cp = ConfigParser()
        cp.read(filename)
        try:
            return float(cp.get("all_modes", "tcold"))
        except Exception as e:
            default = 50.0
            logger.warning("Caught exception %s", e)
            logger.warning("Returning default value %s", default)
            return default

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
            logger.debug("processCalseqScan for DCR")
            # Get DCR FITS DATA 'TIMETAG' column
            # (we only need this for auto mode,
            # but don't want to repeat this in loop)
            dmjds = self.backend.GetIntegrationStartTimes()

            for channel in self.backend.channels:
                for phase in self.backend.GetPhases():
                    logger.debug("channel, phase: %s, %s", channel, phase)
                    self.channels.append(channel)
                    feed = int(channel[0])
                    pol = channel[1]
                    # get the data for that channel
                    channelData = self.backend.GetRawPower(feed, pol, phase)

                    if self.isAuto():  # auto CalSeq
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
                        for datatype in list(autoData.keys()):
                            try:
                                self.scanData[channel].append(
                                    (datatype, numpy.array(autoData[datatype]))
                                )
                            except KeyError:
                                self.scanData[channel] = [
                                    (datatype, numpy.array(autoData[datatype]))
                                ]
                    else:  # manual CalSeq
                        # This is the simple case, all data is the same type
                        calPosition = self.getCalPos()
                        dataType = self.getDataType(calPosition, feed)
                        # Now put data in dict
                        self.scanData[channel] = (dataType, channelData)
        elif self.getBackendName() in ["Spectrometer", "Vegas"]:
            phase = 0

            for beam in self.backend.getBeams():
                for pol in self.backend.getPolarizations():
                    channel = str(beam) + pol[0]
                    self.channels.append(channel)
                    channelData = None
                    if self.isAuto():  # auto CalSeq
                        autoData = {}
                        for ifnum in self.backend.getIFNumbers():
                            # retrieve the needed Spectrometer class
                            bankIdx = self.backend.getBankIndex(
                                beam, pol, ifnum
                            )
                            bank = self.backend.getBank(bankIdx)

                            # Data for stationary wheel positions during scan
                            tint = bank.GetIntegrationTime()
                            dmjds = bank.GetIntegrationStartTimes()
                            for idx, dmjd in enumerate(dmjds):
                                calPosition = self.receiver.getPosition(
                                    dmjd, tint
                                )
                                if calPosition != "Unknown":
                                    dataType = self.getDataType(
                                        calPosition, beam
                                    )
                                    newData = self.backend.getRawPowerByValues(
                                        beam, pol, ifnum, idx, phase
                                    )
                                    if numpy.isnan(newData).any():
                                        continue
                                    try:
                                        autoData[dataType] = numpy.concatenate(
                                            (autoData[dataType], newData)
                                        )
                                    except KeyError:
                                        autoData[dataType] = newData
                        for datatype in list(autoData.keys()):
                            try:
                                self.scanData[channel].append(
                                    (datatype, autoData[datatype])
                                )
                            except KeyError:
                                self.scanData[channel] = [
                                    (datatype, autoData[datatype])
                                ]
                    else:  # manual CalSeq
                        for ifnum in self.backend.getIFNumbers():
                            for i in range(self.backend.getNumIntegrations()):
                                newData = self.backend.getRawPowerByValues(
                                    beam, pol, ifnum, i, phase
                                )
                                try:
                                    channelData = numpy.concatenate(
                                        (channelData, newData)
                                    )
                                except ValueError:
                                    channelData = newData

                        calPosition = self.getCalPos()
                        dataType = self.getDataType(calPosition, beam)
                        self.scanData[channel] = (dataType, channelData)

    def getDataType(self, calPos, feed):
        """Converts cal position Cold1/2 to Vwarm or Vcold depending on feed"""
        if "Cold" in calPos:
            # Convert calPos to key 'Vwarm' or 'Vcold'
            beamLoad = {"Cold1": ("Vcold", "Vwarm"),
                        "Cold2": ("Vwarm", "Vcold")}
            dataType = beamLoad[calPos][feed - 1]
        else:
            dataType = calPos
        return dataType


if __name__ == "__main__":
    projPath = "/home/gbtdata/AGBT16B_288_03"
    scanNum = 1
    scan = CalSeqScan(projPath, scanNum)
    logger.debug("scan: %s", scan)
    scan.processCalseqScan()
