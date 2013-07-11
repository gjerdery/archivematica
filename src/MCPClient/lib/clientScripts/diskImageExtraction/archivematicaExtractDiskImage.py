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
import uuid
import subprocess
import os
import uuid

sys.path.append("/usr/lib/archivematica/archivematicaCommon")
import databaseInterface
from fileOperations import addFileToSIP

class fiwalkFile():
    def __init__(self, file):
        self.partition = file.find("partition").text
        self.inode = file.find("inode").text
        self.filename = file.find("filename").text
        self.xml = file
        self.name_type = file.find("name_type").text
        #self.inode = file.find("inode").text


        
        self.hashdigest={}
        for hashdigest in file.findall("hashdigest"):
            self.hashdigest[hashdigest.get('type')] = hashdigest.text


def getFiwalkFromTransfer(fileUUID, sharedDirectory):
    sql = """SELECT Transfers.currentLocation FROM Transfers JOIN Files ON Files.transferUUID = Transfers.transferUUID WHERE Files.fileUUID = '%s';""" % (fileUUID)
    transferPath = databaseInterface.queryAllSQL(sql)[0][0].replace('%sharedPath%', sharedDirectory, 1)
    
    fiwalkFilePath = os.path.join(transferPath, "logs", "fiwalk-%s.xml" % (fileUUID))
    print fiwalkFilePath 
    tree = etree.parse(fiwalkFilePath)
    return tree.getroot()
   
def main(opts, outputDirectory):
    global exitCode
    exitCode = 0
    fiwalk = getFiwalkFromTransfer(opts.fileUUID, opts.sharedDirectoryPath)
    
    for volume in fiwalk.findall("volume"):
        offset = volume.get('offset')
        volumeDirectory = os.path.join(outputDirectory, "volume %s" % (offset))
        if not os.path.isdir(volumeDirectory):
            os.makedirs(volumeDirectory)

        for file in volume.findall('fileobject'):
            ffile = fiwalkFile(file)
            if ffile.name_type == 'd':
                #todo - empty directories
                continue
            
            command = 'icat -o %(offset)s %(imageFilePath)s %(inode)s' % \
                {'offset':offset, 'imageFilePath':opts.filePath, 'inode':ffile.inode}
            try:
                partition = "partition %s" % (ffile.partition)
                filePath = os.path.join(volumeDirectory, partition, ffile.filename)
                filePathRelativeToSIP = filePath.replace(opts.unitDirectory, "%%%s%%" % (opts.unitReplacementString), 1)
                fileUUID = str(uuid.uuid4())
                print "extracting:{%s}%s" % (fileUUID, filePathRelativeToSIP) 
                dirPath = os.path.dirname(filePath)
                if not os.path.isdir(dirPath):
                    os.makedirs(dirPath)
                file2 = open(filePath, "w")
                p = subprocess.Popen(shlex.split(command), stdin=subprocess.PIPE, stdout=file2, stderr=subprocess.PIPE)
                #p.wait()
                output = p.communicate()
                retcode = p.returncode
                file2.close()
        
                if output[0]:
                    print output[0]
                if output[1] != "":
                    print >>sys.stderr, output[1]
        
                #it executes check for errors
                if retcode != 0:
                    print >>sys.stderr, "error code:" + retcode.__str__()
                    print output[1]# sError
                    #return retcode
                    exitCode+=1
                eventDetail="Unpacked from: {" + opts.fileUUID + "}" + opts.filePath
                addFileToSIP(filePathRelativeToSIP, fileUUID, opts.unitUUID, str(uuid.uuid4), opts.date, sourceType="unpacking", eventDetail=eventDetail, use="diskImageExtractedFile")
            except OSError, ose:
                print >>sys.stderr, "Execution failed:", ose
                #return 1
                exitCode+=1
    return exitCode
