from dcr_table import DcrTable
from astropy.io import fits
import os

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
    'Rcvr69_92',
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
                managerFitsMap[manager] = fits.open(fitsPath)

    return managerFitsMap


fitsForScan = getFitsForScan("/home/archive/science-data/10B/AGBT10B_020_01",
                             4)


data = DcrTable(fitsForScan['DCR'], fitsForScan['IF'])
print(data)
