#! /usr/bin/env python
# -*- coding: utf-8 -*-

import lxml.etree, lxml.html
from optparse import OptionParser
import os
import pprint
import sys

from microtron import *

def parse(argv = None):
    if argv is None:
        argv = sys.argv

    parser = OptionParser('usage: %prog <file> <format>')
    parser.add_option("-s", "--strict",
                  action="store_true", dest="strict", default=False,
                  help="be strict about parsing")
    options, arguments = parser.parse_args(argv[1:])
    if len(arguments) != 2:
        parser.error('Incorrect number of arguments')
        
    source_filename = os.path.abspath(arguments[0])
    format = arguments[1]

    tree = lxml.html.parse(source_filename)
    pprint.pprint(Parser(tree, strict=options.strict).parse_format(format))

if __name__ == '__main__':
    sys.exit(parse())
