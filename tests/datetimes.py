#! /usr/bin/env python
# -*- coding: utf-8 -*-


import unittest

import lxml.etree, lxml.html
from microtron import *
from datetime import datetime,date,time
import os
from pprint import pprint
import pytz
from isodate import tzinfo

class TestDateTime( unittest.TestCase ):
    """tests for the value-class-pattern date parsing functions"""
    def setUp(self):
        self.parser = Parser(None)

    def test_dates(self):
        """test _eval_as_date()"""
        # (input, expected result)
        testdata = (
            # dates:
            # YYYY-MM-DD
            ('2000-01-01', date(2000,01,01)),
            # YYYY-DDD
            ('1977-001', date(1977,01,01)),
        )

        for input,expected in testdata:
            result = self.parser._eval_as_date( input )
            self.assertEqual(result, expected)


    def test_times(self):
        """test _eval_as_time()"""
        testdata = (
            # 24-hour times:
            # HH:MM:SS-XX:YY
            # HH:MM:SS+XX:YY
            # HH:MM:SS-XXYY
            ('1:15:00-0130', time(1,15,0,0,tzinfo.FixedOffset(-1,-30,'-0130'))),
            # HH:MM:SS+XXYY
            ('1:15:00+0130', time(1,15,0,0,tzinfo.FixedOffset(1,30,'+0130'))),
            # HH:MM:SSZ
            ('13:30:00Z', time( 13,30,0,0,tzinfo.Utc())),
            # HH:MM:SS
            ('24:00:00', time(0,0,0)),
            # HH:MM-XX:YY
            # HH:MM+XX:YY
            # HH:MM-XXYY
            # HH:MM+XXYY
            # HH:MMZ
            ('08:25Z', time(8,25,0,0,pytz.utc)),
            # HH:MM
            ('08:25', time(8,25,0)),
            ('24:10', time(0,10,0)),

            #12 hour times:
            # HH:MM:SSam
            ('10:15:53am', time(10,15,53)),
            ('10:15:53a.m.', time(10,15,53)),
            ('12:15:53am', time(0,15,53)),
            # HH:MM:SSpm
            ('10:15:53pm', time(22,15,53)),
            ('10:15:53p.m.', time(22,15,53)),
            ('12:15:53pm', time(12,15,53)),
            # HH:MMam
            ('10:15am', time(10,15,0)),
            ('10:15a.m.', time(10,15,0)),
            # HH:MMpm
            ('10:15pm', time(22,15,0)),
            ('10:15p.m.', time(22,15,0)),
            # HHam
            ('10am', time(10,0,0)),
            ('10AM', time(10,0,0)),
            ('10a.m.', time(10,0,0)),
            ('2a.m.', time(2,0,0)),
            ('12a.m.', time(0,0,0)),
            # HHpm 
            ('10pm', time(22,0,0)),
            ('10PM', time(22,0,0)),
            ('10P.M.', time(22,0,0)),
            ('2p.m.', time(14,0,0)),
            ('12p.m.', time(12,0,0)),
        )

        for input,expected in testdata:
            result = self.parser._eval_as_time(input)
            self.assertEqual(result, expected)


    def test_timezones(self):
        """test _eval_as_tzinfo()"""
        testdata = (
            # timezones
            # -XX:YY
            ('-05:00', tzinfo.FixedOffset(-5,0,'-0500')),
            # +XX:YY
            ('+05:00', tzinfo.FixedOffset(5,0,'+05:00')),
            # -XXYY
            ('-0500', tzinfo.FixedOffset(-5,-0,'-0500')),
            ('-0530', tzinfo.FixedOffset(-5,-30,'-0530')),
            # +XXYY
            ('+0500', tzinfo.FixedOffset(5,0,'+0500')),
            # -XX
#            ('-08', tzinfo.FixedOffset(8,0,'-08')),
            # +XX
#            ('+08', tzinfo.FixedOffset(8,0,'+08')),
            # Z
            ( 'Z', tzinfo.Utc() )
        )
        for input,expected in testdata:
            result = self.parser._eval_as_tzinfo(input)
            self.assertEqual(time(0,0,0,0,result), time(0,0,0,0,expected))

if __name__ == '__main__':
    unittest.main()
