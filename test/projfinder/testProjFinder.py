from datetime import date, timedelta
import os
import shutil
import tempfile
import unittest
from mock import patch

from projFinder import (
    getYearAbbrev,
    yearIsValid,
    ProjectFinder
)
# import projFinder


class TestGetYearAbbrev(unittest.TestCase):
    def testFullYear(self):
        self.assertEqual(getYearAbbrev(2017), 17)
        self.assertEqual(getYearAbbrev(10123), 23)

    def testNegativeYear(self):
        with self.assertRaises(ValueError):
            getYearAbbrev(-2017)

    def testAbbrevYear(self):
        self.assertEqual(getYearAbbrev(0), 0)
        self.assertEqual(getYearAbbrev(17), 17)


class TestYearIsValid(unittest.TestCase):
    def testValidYear(self):
        self.assertTrue(yearIsValid(2017))

    def testTooEarlyYear(self):
        self.assertFalse(yearIsValid(1900))

    def testTooLateYear(self):
        tooLateYear = date.today() + timedelta(days=366)
        self.assertFalse(yearIsValid(tooLateYear.year))


class TestProjectFinder(unittest.TestCase):

    def setUp(self):
        self.pf = ProjectFinder()
    def testNoArgs(self):
        with self.assertRaises(TypeError):
            pf = ProjectFinder()
            pf.search()

    def testOnlyRcvr(self):
        dirs = self.pf.search(["Rcvr1_2"])

    def testRcvrAndBackend(self):
        dirs = self.pf.search(["RcvrArray75_115", "DCR"])

    def testNoGbtdata(self):
        # TODO: Fix this; it doesn't handle the case where there is a dir
        # but no scan log
        dirs = self.pf.search(["Rcvr1_2"], searchGbtdata=False)

    def testNoArchiveData(self):
        dirs = self.pf.search(["Rcvr1_2"], searchArchive=False)

    def testSearchAll(self):
        dirs = self.pf.search(["Rcvr1_2"], searchAll=True)
