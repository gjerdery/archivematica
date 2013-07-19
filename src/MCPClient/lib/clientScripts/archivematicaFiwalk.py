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
# @subpackage archivematicaClientScript
# @author Joseph Perry <joseph@artefactual.com>
import sys
import shlex
import lxml.etree as etree
import subprocess
import os
from diskImageExtraction.archivematicaExtractDiskImageFunctionsLibrary import getTSKImages

sys.path.append("/usr/lib/archivematica/archivematicaCommon")
#import databaseInterface


if __name__ == '__main__':
    global exitCode
    exitCode = 0
    target = sys.argv[1]
    date = sys.argv[2]
    eventUUID = sys.argv[3]
    fileUUID  = sys.argv[4]

    
    command = "fiwalk -x \"" + getTSKImages(target) + "\" -c /usr/lib/archivematica/archivematicaCommon/externals/fiwalkPlugins/ficonfig.txt"
    print >>sys.stderr, command
    print >>sys.stderr,  shlex.split(command)
    try:
        p = subprocess.Popen(shlex.split(command), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        #p.wait()
        output = p.communicate()
        retcode = p.returncode

        if output[0] != "":
            print output[0]
        if output[1] != "":
            print >>sys.stderr, output[1]
        
        #it executes check for errors
        if retcode != 0:
            print >>sys.stderr, "error code:" + retcode.__str__()
            print output[1]# sError
            #return retcode
            quit(retcode)
        #try:
        #tree = etree.XML(output[0])
        #print etree.tostring(tree, pretty_print=True )
        #except:
            #print >>sys.stderr, "Failed to read Fits's xml."
            #exit(2)
        exit(retcode)

    except OSError, ose:
        print >>sys.stderr, "Execution failed:", ose
        #return 1
        exit(1)
    exit(exitCode)
