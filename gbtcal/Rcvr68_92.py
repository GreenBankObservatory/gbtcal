# Copyright (C) 2011 Associated Universities, Inc. Washington DC, USA.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Correspondence concerning GBT software should be addressed as follows:
#       GBT Operations
#       National Radio Astronomy Observatory
#       P. O. Box 2
#       Green Bank, WV 24944-0002 USA

import logging
import traceback

from astropy.io import fits


logger = logging.getLogger(__name__)


class Rcvr68_92:
    """
    Represents the calibration data taken by the W-band Receiver during a scan.
    """

    def __init__(self, fitsData, debug=False):

        self.fitsData = fitsData

        # these are the possible CALPOS values, in order, i.e.
        # 0=="Observing, 1=="Cold1", etc.
        # anything not from this when the motion value is not set is "Unknown"
        self.calPosTypes = ["Observing", "Cold1",
                            "Position2", "Position3", "Cold2", "Position5"]

        self.lastQueriedDMJD = 0.0
        self.lastQueriedIndex = -1

        self.hasTable = False

        self.debug = debug

        self.readInfo()

    def readInfo(self):
        "Read in keywords and columns from data"

        # default values
        self.fitsver = '0.0'
        self.calSeq = 'Unknown'
        self.calPos = 'Unknown'
        nanValue = float('NaN')
        self.tcold = nanValue
        self.twarm = nanValue
        self.dmjds = []
        self.moving = []
        self.tcoldCol = []
        self.twarmCol = []
        self.positions = []
        self.scanFinished = True

        self.timeIndexes = {}

        if self.fitsData is None:
            return

        try:
            self.scanFinished = False

            # protection against missing or mal-formed primary header
            # fitsData = pyfits.open(self.data.getFilename('Rcvr68_92'))
            # fitsData = fits.open(self.filepath)

            # primary HDU keywords
            pHeader = self.fitsData[0].header

            # if pHeader.has_key('fitsver'):
            keys = [k.lower() for k in pHeader.keys()]
            if 'fitsver' in keys:
                self.fitsver = pHeader['fitsver']
            elif self.debug:
                logger.debug("FITSVER keyword missing")

            # if pHeader.has_key('calseq'):
            if 'calseq' in keys:
                calSeqKW = pHeader['calseq']
                if calSeqKW == 1:
                    self.calSeq = 'auto'
                elif calSeqKW == 0:
                    self.calSeq = 'manual'
                else:
                    self.calSeq = 'Unknown'
                    if self.debug:
                        logger.debug("unexpected CALSEQ value: %d", calSeqKW)
            elif self.debug:
                logger.debug("missing CALSEQ keyword")

            # if pHeader.has_key('calpos'):
            if 'calpos' in keys:
                calPosKW = pHeader['calpos']
                if type(calPosKW) is not str:
                    self.calPos = self.getCalPosString(calPosKW)
                    if self.debug:
                        logger.debug("CALPOS KW is integer")
                else:
                    self.calPos = calPosKW
            elif self.debug:
                logger.debug("missing CALPOS keyword")

            # if pHeader.has_key('tcold'):
            if 'tcold' in keys:
                self.tcold = pHeader['tcold']
            elif self.debug:
               logger.debug("missing TCOLD keyword")

            # if pHeader.has_key('twarm'):
            if 'twarm' in keys:
                self.twarm = pHeader['twarm']
            elif self.debug:
               logger.debug("missing TWARM keyword")

            # binary table
            if len(self.fitsData) > 1:
                tabData = self.fitsData[1].data
                if tabData is not None:
                    colNames = tabData.names
                    for i in range(len(colNames)):
                        colNames[i] = colNames[i].lower()

                    if 'timestamp' in colNames:
                        self.dmjds = tabData.field('timestamp')
                        if self.debug:
                            logger.debug("TimeStamp column used")
                    elif 'dmjd' in colNames:
                        self.dmjds = tabData.field('dmjd')
                    elif self.debug:
                        logger.debug("missing a time column of either type")

                    if len(self.dmjds) > 0:
                        if 'motion' in colNames:
                            self.moving = tabData.field('motion')
                        else:
                            # assume no motion
                            for i in range(self.dmjds):
                                self.moving.append(False)
                            if self.debug:
                                logger.debug("missing MOTION column")

                        if 'position' in colNames:
                            positionCol = tabData.field('position')
                        else:
                            # default to CALPOS keyword value
                            positionCol = []
                            for i in range(self.dmjds):
                                positionCol.append(self.calPos)
                            if self.debug:
                                logger.debug("missing POSITION column")

                        if 'tcold' in colNames:
                            self.tcoldCol = tabData.field('tcold')
                        else:
                            # default to TCOLD KW value
                            for i in range(self.dmjds):
                                self.tcoldCol.append(self.tcold)
                            if self.debug:
                                logger.debug("missing TCOLD column")

                        if 'twarm' in colNames:
                            self.twarmCol = tabData.field('twarm')
                        else:
                            # default to TWARM KW value
                            for i in range(self.dmjds):
                                self.twarmCol.append(self.twarm)
                            if self.debug:
                                logger.debug("missing TWARM column")

                        if 'endofscan' in colNames:
                            self.scanFinished = tabData.field(
                                'endofscan')[-1] == 1
                        else:
                            # need to assume it's finished
                            self.scanFinished = True
                            if self.debug:
                                logger.debug("missing EndOfScan column")

                        self.hasTable = True
                    elif self.debug:
                        # otherwise there is no time column
                        # ignore anything that might be in this table
                        logger.debug("empty table.")
                else:
                    # it might have not yet been written
                    self.scanFinished = False
                    if self.debug:
                        logger.debug("problem with data field of hdu[1]")
            else:
                # it might have not yet been written
                self.scanFinished = False
                if self.debug:
                    logger.debug("missing table.")

            self.fitsData.close()

            # translate POSITION column values to string if they aren't already
            if len(self.dmjds) > 0:
                if type(positionCol[0]) is str:
                    self.positions = positionCol
                else:
                    # translate intPositions to strings
                    self.positions = []
                    for i in range(len(positionCol)):
                        self.positions.append(
                            self.getCalPosString(positionCol[i]))
                    if self.debug:
                        logger.debug("POSITION column translated to string values")
            else:
                self.positions = []

            if self.debug:
                if not self.isAuto() and self.calPos not in self.calPosTypes and self.calPos != "Unknown":
                    logger.warning("unrecognized CALPOS keyword value %s", self.calPos)

                for thisPos in self.positions:
                    if thisPos not in self.calPosTypes and thisPos != "Unknown":
                        logger.warning("unrecognized POSITION column value %s", thisPos)
        except Exception:
            # nothing to do except move on
            self.scanFinished = True
            if self.debug:
                logger.warning("unexpected exception parsing Rcvr68_92 FITS file")
                traceback.print_exc()

        logger.debug("finished readInfo")

    def getCalPosString(self, calPosInt):
        result = "Unknown"
        if calPosInt >= 0 and calPosInt < len(self.calPosTypes):
            result = self.calPosTypes[calPosInt]
        return result

    def isAuto(self):
        return self.calSeq == 'auto'

    def getCalpos(self):
        # return the CALPOS keyword value
        return self.calPos

    def numrows(self):
        """The number of available rows in the binary table."""
        if self.hasTable:
            return len(self.positions)
        return 0

    def getPosition(self, dmjd=None, duration=None):
        """
        Find the position at DMJD (days).
        If it was moving (using duration to give a range) then return 'Unknown'
        """
        # if manual, return first row value else keyword value if table empty
        result = "Unknown"

        if not self.isAuto():
            if self.numrows() > 0:
                result = self.positions[0]
            else:
                # no table, use keyword
                result = self.calPos
        else:
            # auto scan
            if self.isMoving(dmjd, duration):
                result = "Unknown"
            else:
                index = self.getIndexFromDMJD(dmjd)
                if index >= 0:
                    result = self.positions[index]
                else:
                    result = "Unknown"
        return result

    def getPol(self, linearPol, feed, calPosition):
        """
        Translate the linear polarization to the appropriate one given the
        CALPOSITION and feed
        """
        # linearPol is the FITS code, returns a FITS code
        # XX : -5 YY: -6 XY: -7  XY: -8
        # RR : -1 LL: -2 RL: -3  LR: -4
        result = linearPol
        if self.filepath is not None:
            if (calPosition == "Position2" and feed == 1 or
                    calPosition == "Position5" and feed == 2):
                # X->L, Y->R
                if linearPol == -5:
                    result = -2
                elif linearPol == -6:
                    result = -1
                elif linearPol == -7:
                    result = -4
                elif linearPol == -8:
                    result = -3
                else:
                    logger.warning("Rcvr68_92: Unrecognized polarization code %s", linearPol)

        return result

    def isMoving(self, dmjd=None, duration=None):
        """
        Was the table moving at DMJD (days). Duration (s) defines a range,
        true if moving at any time during that range.
        Manual scans are by definition not moving.
        """
        if not self.isAuto():
            return False

        if dmjd is None or duration is None:
            # it's an AUTO scan but without time and duration we can't know,
            # assuming moving
            return True

        # if it gets here, it's an AUTO scan. moving is a possibility.
        halfDurationDays = duration / (24.0 * 60.0 * 60.0) / 2.0
        startTime = dmjd - halfDurationDays
        stopTime = dmjd + halfDurationDays
        startIndex = self.getIndexFromDMJD(startTime)
        stopIndex = self.getIndexFromDMJD(stopTime)
        if startIndex == stopIndex:
            if startIndex < 0:
                result = False
            else:
                result = self.moving[startIndex]
        else:
            # if they are both < 0, they should both be -1 and caught above
            result = False
            if startIndex < 0:
                # assume it wasn't moving before the scan started
                startIndex = 0
            if stopIndex < 0:
                # use last row
                stopIndex = self.numrows() - 1
            for i in range(startIndex, stopIndex + 1):
                result = result or self.moving[i]
                if result:
                    break
        return result

    def getTcold(self, dmjd=None):
        """Return TCOLD at or immediately before DMJD (days).
        For manual scans, use first row in table if it exists,
        else the TCOLD keyword value.
        """
        # default to TCOLD KW value
        result = self.tcold
        if not self.isAuto():
            # manual scan, return first row value if it exists
            if self.hasTable:
                result = self.tcoldCol[0]
        else:
            index = self.getIndexFromDMJD(dmjd)
            if index >= 0:
                result = self.tcoldCol[index]

        return result

    def getTwarm(self, dmjd=None):
        """
        Return TWARM at or immediately before DMJD (days).
        For manual scans, use first row in table if it exists,
        else the TWARM keyword value.
        """
        # default to TWARM KW value
        result = self.twarm
        if not self.isAuto():
            # manual scan, return first row value if it exists
            if self.hasTable:
                result = self.twarmCol[0]
        else:
            index = self.getIndexFromDMJD(dmjd)
            if index >= 0:
                result = self.twarmCol[index]

        return result

    def getIndexFromDMJD(self, dmjd):
        # do not interpolate, try and use past values to shorten search time
        if dmjd is None:
            return -1

        if len(self.dmjds) == 0:
            return -1

        if dmjd > self.lastQueriedDMJD:
            # move ahead
            nextIndex = self.lastQueriedIndex + 1
            if nextIndex < len(self.dmjds):
                # still times to look at
                for i in range(nextIndex, len(self.dmjds)):
                    if dmjd < self.dmjds[i]:
                        break
                    self.lastQueriedIndex = i
        elif dmjd < self.lastQueriedDMJD:
            # go backwards
            pastIndex = self.lastQueriedIndex
            if pastIndex >= 0:
                for i in range(pastIndex, -1, -1):
                    self.lastQueriedIndex = i
                    if dmjd > self.dmjds[i]:
                        break

            if dmjd < self.dmjds[0]:
                # before the start of the file if this is still true
                self.lastQueriedIndex = -1

        # else it is equal and the last values are good to use
        self.lastQueriedDMJD = dmjd
        self.timeIndexes[dmjd] = self.lastQueriedIndex

        return self.lastQueriedIndex


if __name__ == "__main__":
    fn = "/home/gbtdata/AGBT16B_288_03/Rcvr68_92/2017_02_27_08:59:51.fits"
    w = Rcvr68_92(fn, debug=True)
    logger.debug(w)
    logger.debug(w.dmjds)
    logger.debug(w.twarmCol)
