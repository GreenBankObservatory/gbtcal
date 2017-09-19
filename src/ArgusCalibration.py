import os
import numpy
from astropy.io import fits

TEMP_OFFSET = 273.15


class ArgusCalibration:
    """
    A class which handles the calibration (or not) of Argus data.
    od is the ObsDir object which allows this class to access fits files.
    vane is the scan number of the vane scan.
    sky is the scan number of the sky scan.
    """
    def __init__(self, path, vane, sky):
        self.projpath = path
        print "Argus Cal: vane scan = {}, sky scan = {}".format(vane, sky)
        self.vanefile = vane
        self.skyfile = sky

    def getTwarm(self):
        """Read the RcvrArray75_115 FITS file for the TWARM header keyword."""
        filepath = os.path.join(self.projpath, "RcvrArray75_115", self.vanefile)
        header = fits.open(filepath)[0].header
        return header["TWARM"] + TEMP_OFFSET

    def getVwarm(self):
        """Read the DCR FITS file DATA for VANE scan, and take the median."""
        filepath = os.path.join(self.projpath, "DCR", self.vanefile)
        data = fits.open(filepath)[3].data["DATA"]
        return numpy.median(data[:, 0]), numpy.median(data[:, 1])

    def getVcold(self):
        """Read the DCR FITS file DATA for SKY scan, and take the median."""
        filepath = os.path.join(self.projpath, "DCR", self.skyfile)
        data = fits.open(filepath)[3].data["DATA"]
        return numpy.median(data[:, 0]), numpy.median(data[:, 1])

    def getGain(self):
        """Compute the gain values using information from FITS files."""
        twarm = self.getTwarm()
        vwarm = self.getVwarm()
        vcold = self.getVcold()
        gains = twarm / (vwarm[0] - vcold[0]), twarm / (vwarm[1] - vcold[1])
        return {"X10": gains[0], "X11": gains[1]}
