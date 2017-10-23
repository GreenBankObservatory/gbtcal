#! /usr/bin/env/python
# -*- coding: utf-8 -*-

import argparse
import logging
import os
from glob import iglob
from datetime import date
import re

from astropy.io import fits
from astropy.table import Table, Column
import numpy
"""docstring"""

# TODO: Remove
logging.basicConfig(level=logging.DEBUG)

class ProjectFinder(object):
    def __init__(self, dataPaths=None, archiveDirs=None):
        self.archivePath = "/home/archive"
        self.gbtdataPath = "/home/gbtdata"

        self.dataPaths = {
            "archive": "/home/archive",
            "gbtdata": "/home/gbtdata"
        }
        # TODO: Handle VLA, etc. data
        self.prefixes = {
            'science-data': 'AGBT',
            'test-data': 'TGBT',
            'junk-data': 'JGBT'
        }

        self.archiveDirs = {
            "science-data": {
                "prefix": "AGBT",
                "name": "science-data",
            },
            "test-data": {
                "prefix": "TGBT",
                "name": "test-data"
            }
        }

        self.semesterGlob = r'[0-9][0-9][ABCD]'
        self.semesterPattern = r'^(?P<year>\d{2})(?P<code>[ABCD])$'


    def getPathsWithinYearRange(self, path,
                                minYearAbbrev=None, maxYearAbbrev=None):
        matchingPaths = []
        semesterPaths = iglob(os.path.join(path, self.semesterGlob))
        for semesterPath in semesterPaths:
            # For each of those we pull out their semester (in order
            # to get their year component)...
            semester = re.match(self.semesterPattern,
                                os.path.basename(semesterPath))

            if semester:
                year = semester.groupdict()['year']
            else:
                raise ValueError("Given semester must match pattern {},"
                                 "e.g. '17A'")
            # Determine whether we should be searching
            # this semester or not
            searchThisSemester = False
            if minYearAbbrev is not None and maxYearAbbrev is not None:
                # If we have both min and max years we must search
                # between them
                if year >= minYearAbbrev and year <= maxYearAbbrev:
                    searchThisSemester = True
            elif minYearAbbrev is None and maxYearAbbrev is not None:
                # If we have only a max year we use only an upper bound
                if year <= maxYearAbbrev:
                    searchThisSemester = True
            elif minYearAbbrev is not None and maxYearAbbrev is None:
                # If we have only a min year we use only a lower bound
                if year >= minYearAbbrev:
                    searchThisSemester = True
            else:
                raise ValueError("At least one of minYear or maxYear "
                                 "must be provided")

            if searchThisSemester:
                matchingPaths.extend(iglob(os.path.join(semesterPath, "*")))

        return matchingPaths

    def getArchiveFolderPaths(self, folder, minYear=None, maxYear=None):
        """Given a path to an archive folder...

        Archive folders have a specific structure. They contain semester data
        in the format 17A, 17B, etc. We use this structure to easily
        filter archive data by year in our searches
        """
        minYearAbbrev = getYearAbbrev(minYear) if minYear is not None else None
        maxYearAbbrev = getYearAbbrev(maxYear) if maxYear is not None else None
        if minYearAbbrev is None and maxYearAbbrev is None:
            # If no semester filter is being applied then we just
            # search everything.
            return iglob("{}/**/*".format(folder))
        else:
            # If we do have a semester filter, then we glob all of the
            # matching semester subfolders
            return self.getPathsWithinYearRange(minYearAbbrev, maxYearAbbrev)

    def getArchivePaths(self, foldersToSearch=None):
        if not foldersToSearch:
            foldersToSearch = getDirs(self.archivePath)

        paths = []
        for folder in foldersToSearch:
            archiveFolderPath = os.path.join(self.archivePath, folder)
            logging.debug("Gathering paths from archive folder %s...", folder)
            paths.extend(self.getArchiveFolderPaths(archiveFolderPath))
            logging.debug("...done gathering paths from archive folder %s...",
                          folder)
        return [p for p in paths if os.path.isdir(p)]

    def getGbtdataPaths(self, obsData=True, testData=True):
        gbtdataPath = self.dataPaths['gbtdata']
        globs = []
        if obsData:
            obsPrefix = self.prefixes['science-data']
            globs.append("{}/{}*".format(gbtdataPath, obsPrefix))
        if testData:
            testDataPrefix = self.prefixes['test-data']
            globs.append("{}/{}*".format(gbtdataPath, testDataPrefix))

        paths = []
        for glob in globs:
            paths.extend(iglob(glob))
        return [p for p in paths if os.path.isdir(p)]


    def search(self, managers, obsData=True, testData=False,
               minYear=None, maxYear=None, semester=None,
               searchAll=False, searchArchive=True,
               searchGbtdata=True, stopAfterFirstMatch=True):
        # TODO: Not good enough! Doesn't search anything other than science
        # and test data still, although it does search all semesters
        if searchAll:
            obsData = True
            testData = True
            minYear = None
            maxYear = None
            searchArchive = True
            searchGbtdata = True

        if not obsData and not testData:
            raise ValueError("Your must specify at least one of "
                             "obsData or testData!")


        # TODO: semester not yet handled
        if semester and not re.match(self.semesterPattern, semester):
            raise ValueError("semester must be of the form {}, e.g. '17A'"
                             .format(self.semesterPattern))

        projectPathsToSearch = []
        if searchGbtdata:
            logging.debug("Gather paths from gbtdata...")
            projectPathsToSearch.extend(self.getGbtdataPaths(obsData, testData))
            logging.debug("...done gathering paths from gbtdata")


        # if minYearAbbrev is not None or maxYearAbbrev is not None:
        if searchArchive:
            logging.debug("Gather paths from archive...")
            projectPathsToSearch.extend(self.getArchivePaths(["science-data", "test-data"]))
            logging.debug("...done gathering paths from archive")

        projInfos = []
        logging.debug("Searching for projects that contain data from all of: %s",
                      managers)
        for path in projectPathsToSearch:
            try:
                projContents = getDirs(path)
            except OSError as error:
                logging.warning(error)
                # if error.errno == 13:
                #     logging.warning("Permission denied: %s", path)
                # else:
                #     raise
            # import ipdb; ipdb.set_trace()
            # If we have a match...
            if set(projContents).issuperset(managers):
                scanNum, scanName = searchForScan(path, managers)
                if scanNum and scanName:
                    projInfos.append((path, scanNum, scanName))
                    logging.info("%s contains data from all of: %s",
                                 path, managers)

                    if stopAfterFirstMatch:
                        return projInfos

            # projInfos.extend(iglob(os.path.join(path, managers)))

        return projInfos

def searchForScan(projPath, managers):
    scanLogPath = os.path.join(projPath, "ScanLog.fits")
    scanLogFits = fits.open(scanLogPath)
    scanLogTable = parseScanLog(scanLogFits)

    scans = numpy.unique(scanLogTable['SCAN'])
    for scan in scans:
        scanMask = scanLogTable['SCAN'] == scan
        dataForScan = scanLogTable[scanMask]
        # If all managers are present (i.e. took data, in a perfect world)
        # in this scan...
        if numpy.all(numpy.in1d(managers, dataForScan['MANAGER'])):
            allFilesActuallyExist = True
            managersForScan = [m for m in numpy.unique(dataForScan['MANAGER'])
                               if m]
            for manager in managersForScan:
                managerRow = dataForScan[dataForScan['MANAGER'] == manager][0]
                # import ipdb; ipdb.set_trace()
                managerFitsPath = os.path.join(projPath,
                                               manager,
                                               managerRow['FITSNAME'])
                if not os.path.isfile(managerFitsPath):
                    print("FILE DOES NOT EXIST: {}".format(managerFitsPath))
                    allFilesActuallyExist = False
                else:
                    print("FILE EXISTS: {}".format(managerFitsPath))

            if allFilesActuallyExist:
                # We simply return the first scan we find
                return (scan, dataForScan['FITSNAME'][0])

    # If we get here, we have failed to find a scan in which all of the
    # given managers appear
    return (None, None)

# TODO: This should be imported!
def stripTable(table):
    """Given an `astropy.table`, strip all of its string-type columns
    of any right-padding, in place.
    """
    for column in table.columns.values():
        # If the type of this column is String or Unicode...
        if column.dtype.char in ['S', 'U']:
            # ...replace its data with a copy in which the whitespace
            # has been stripped from the right side
            stripped_column = Column(name=column.name,
                                     data=numpy.char.rstrip(column))
            # print("Replacing column {} with stripped version"
            #       .format(column.name))
            table.replace_column(column.name, stripped_column)

def parseScanLog(scanLogFits):
    slt = Table.read(scanLogFits)
    stripTable(slt)
    managers = []
    fitsNames = []
    for row in slt:
        if "SCAN " not in row['FILEPATH']:
            _, _, manager, name = row['FILEPATH'].split("/")
            managers.append(manager)
            fitsNames.append(name)
        else:
            managers.append('')
            fitsNames.append('')

    slt.add_column(Column(name='MANAGER', data=managers, dtype=str))
    slt.add_column(Column(name='FITSNAME', data=fitsNames, dtype=str))
    return slt


def getDirs(path):
    return [f for f in os.listdir(path)
            if os.path.isdir(os.path.join(path, f))]

def getYearAbbrev(year):
    if year < 0:
        raise ValueError("year must be positive!")

    return int(str(year)[-2:])


def yearIsValid(year):
    currYearAbbrev = getYearAbbrev(date.today().year)
    return (
        year in range(2000, date.today().year + 1) or
        year in range(getYearAbbrev(2000), currYearAbbrev + 1)
   )

def main():
    pass


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose",
                        action="store_true",
                        help="Provide more verbose output")
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    main()
