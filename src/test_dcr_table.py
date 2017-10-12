from dcr_table import DcrTable
from dcr_decode import RCVRS, getFitsForScan
from astropy.io import fits
import os


fitsForScan = getFitsForScan("/home/archive/science-data/10B/AGBT10B_020_01",
                             4)


data = DcrTable(fitsForScan['DCR'], fitsForScan['IF'])
