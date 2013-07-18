#!/usr/bin/python -OO
# This file is part of Archivematica.
#
# Copyright 2010-2013 Artefactual Systems Inc. <http://artefactual.com>
#
# Archivematica is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Archivematica is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Archivematica.  If not, see <http://www.gnu.org/licenses/>.

# @package Archivematica
# @subpackage transcoder
# @author Joseph Perry <joseph@artefactual.com>

import sys
import os
import uuid
from diskImageExtraction.archivematicaExtractDiskImage import main
sys.path.append("/usr/lib/archivematica/archivematicaCommon")
import databaseInterface

global extractedCount


def parseOptions():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-p",  "--filePath", action="store", dest="filePath", default="")
    parser.add_option("-u",  "--unitDirectory", action="store", dest="unitDirectory", default="") 
    parser.add_option("-i",  "--unitUUID", action="store", dest="unitUUID", default="")
    parser.add_option("-d",  "--date", action="store", dest="date", default="")
    parser.add_option("-t",  "--taskUUID", action="store", dest="taskUUID", default="")
    parser.add_option("-f",  "--fileUUID", action="store", dest="fileUUID", default="")
    parser.add_option("-r",  "--unitReplacementString", action="store", dest="unitReplacementString", default="")
    parser.add_option("-s",  "--sharedDirectoryPath", action="store", dest="sharedDirectoryPath", default="/var/archivematica/sharedDirectory/") 
    return parser.parse_args()

if __name__ == '__main__':
    exitCode = 0
    while False:
        import time
        time.sleep(10)
    (opts, args) = parseOptions()
    print opts.filePath
    date = opts.date.split(".", 1)[0]
    replacementDic = { \
        "%inputFile%": opts.filePath, \
        "%outputDirectory%": opts.filePath + '-' + date \
        }

    basename = opts.filePath
    fileName, ext = os.path.splitext(basename)
    ext = ext.lower()
    if ext in ['.iso', '.e01', '.dmg', '.ad1', '.dsk', '.img', '.bin', '.raw', '.dd.001', '.001', '.i00']:
        outputDirectory = replacementDic['%outputDirectory%'] 
        exitCode += main(opts, outputDirectory)
        
    exit(exitCode)

