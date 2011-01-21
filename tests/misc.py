#! /usr/bin/env python
# -*- coding: utf-8 -*-


import unittest

import lxml.etree, lxml.html
from microtron import *
from datetime import datetime,date,time
import os
from pprint import pprint
#import pytz
from StringIO import StringIO



class TestDateTime(unittest.TestCase):

    def setUp(self):

        # dummy microformat definition for testing datetimes
        dummy_fmt = """<!-- blah -->
<microformats>
  <dummy type="compound">
    <updated mandatory="yes" type="datetime"/>
  </dummy>
</microformats>
"""
        self.formats = lxml.etree.parse( StringIO( dummy_fmt ) )



    def test_dates(self):
        test_data = [
            ("""published on <span class="value">2009-08-01</span> at <span class="value">12:06</span>""", datetime(2009,8,1,12,6) ),
            ("""<span class="value">2009-08-01</span>""", datetime(2009,8,1) ),
        ]

        for txt,expected in test_data:
            wrapped = """<div class="dummy">\n<span class="updated">\n%s\n</span>\n</div>\n""" % (txt,)
            doc = lxml.html.fromstring( wrapped )
            parser = Parser(doc, self.formats, strict=True )
            result = parser.parse_format('dummy')

            self.assertEqual( result[0]['updated']['datetime'], expected )

if __name__ == '__main__':
    unittest.main()

