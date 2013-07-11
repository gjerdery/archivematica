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
from executeOrRunSubProcess import executeOrRun
from fileOperations import addFileToTransfer
from databaseFunctions import fileWasRemoved
from fileOperations import updateSizeAndChecksum
import databaseInterface

global extractedCount
extractedCount = 1
removeOnceExtracted = True


def onceExtracted(command):
    extractedFiles = []
    print "TODO - Metadata regarding removal of extracted archive"
    if removeOnceExtracted:
        packageFileUUID = opts.fileUUID
        sipDirectory = opts.unitDirectory
        os.remove(replacementDic["%inputFile%"])
        currentLocation =  replacementDic["%inputFile%"].replace(sipDirectory, "%%%s%%" % (opts.unitReplacementString), 1)
        fileWasRemoved(packageFileUUID, eventOutcomeDetailNote = "removed from: " + currentLocation)

    print "OUTPUT DIRECTORY: ", replacementDic["%outputDirectory%"]
    for w in os.walk(replacementDic["%outputDirectory%"].replace("*", "asterisk*")):
        path, directories, files = w
        for p in files:
            p = os.path.join(path, p)
            #print "path: ", p
            if os.path.isfile(p):
                extractedFiles.append(p)
    for ef in extractedFiles:
        fileUUID = uuid.uuid4().__str__()
        #print "File Extracted:", ef
        if True: #Add the file to the SIP
            #<arguments>"%relativeLocation%" "%SIPObjectsDirectory%" "%SIPLogsDirectory%" "%date%" "%taskUUID%" "%fileUUID%"</arguments>
            sipDirectory = opts.unitDirectory
            transferUUID = opts.unitUUID
            date = opts.date
            taskUUID = opts.taskUUID
            packageFileUUID = opts.fileUUID

            filePathRelativeToSIP = ef.replace(sipDirectory,"%%%s%%" % (opts.unitReplacementString), 1)
            print "File Extracted:: {" + fileUUID + "} ", filePathRelativeToSIP
            eventDetail="Unpacked from: {" + packageFileUUID + "}" + filePathRelativeToSIP
            if "transferDirectory" == opts.unitReplacementString:
                addFileToTransfer(filePathRelativeToSIP, fileUUID, transferUUID, taskUUID, date, sourceType="unpacking", eventDetail=eventDetail)
            elif "sipDirectory" == opts.unitReplacementString:
                addFileToSIP(filePathRelativeToSIP, fileUUID, transferUUID, taskUUID, date, sourceType="unpacking", eventDetail=eventDetail)
            else:
                print >>sys.stderr, "INVALID opts.unitReplacementString"
                raise
            updateSizeAndChecksum(fileUUID, ef, date, uuid.uuid4.__str__())


        run = sys.argv[0].__str__() + \
        " \"" + transcoder.escapeForCommand(ef) + "\""
        if True: #Add the file to the SIP
            run = run + \
            " --filePath \"%s\"" % (ef) + \
            " --unitDirectory \"%s\"" % (opts.unitDirectory)  + \
            " --unitUUID \"%s\"" % (opts.unitUUID)  + \
            " --date \"%s\"" % (opts.date)  + \
            " --taskUUID \"%s\"" % (uuid.uuid4.__str__())  + \
            " --fileUUID \"%s\"" % (fileUUID)  + \
            " --unitReplacementString \"%s\"" % (opts.unitReplacementString)  
        exitCode, stdOut, stdError = executeOrRun("command", run)
        print stdOut
        print >>sys.stderr, stdError
        if exitCode != 0 and command.exitCode == 0:
            command.exitCode = exitCode

    global extractedCount
    date = sys.argv[4].__str__().split(".", 1)[0]
    extractedCount = extractedCount + 1
    replacementDic["%outputDirectory%"] = transcoder.fileFullName + '-' + extractedCount.__str__() + '-' + date

def identifyCommands(fileName):
    """Identify file type(s)"""
    ret = []
    removeOnceExtractedSkip = ['.part01.rar', '.r01', '.pst']

    RarExtensions = ['.part01.rar', '.r01', '.rar']
    for extension in RarExtensions:
        if fileName.lower().endswith(extension.lower()):
            #sql find the file type,
            sql = """SELECT CR.pk, CR.command, CR.GroupMember
            FROM CommandRelationships AS CR
            JOIN FileIDs ON CR.fileID=FileIDs.pk
            JOIN CommandClassifications ON CR.commandClassification = CommandClassifications.pk
            WHERE FileIDs.description='unrar-nonfreeCompatable'
            AND CommandClassifications.classification = 'extract';"""
            databaseInterface.runSQL(sql)
            while row != None:
                ret.append(row)
                row = c.fetchone()
            break

    SevenZipExtensions = ['.ARJ', '.CAB', '.CHM', '.CPIO',
                  '.DMG', '.HFS', '.LZH', '.LZMA',
                  '.NSIS', '.UDF', '.WIM', '.XAR',
                  '.Z', '.ZIP', '.GZIP', '.TAR',]
    for extension in SevenZipExtensions:
        if fileName.lower().endswith(extension.lower()):
            sql = """SELECT CR.pk, CR.command, CR.GroupMember
            FROM CommandRelationships AS CR
            JOIN FileIDs ON CR.fileID=FileIDs.pk
            JOIN CommandClassifications ON CR.commandClassification = CommandClassifications.pk
            WHERE FileIDs.description='7ZipCompatable'
            AND CommandClassifications.classification = 'extract';"""
            databaseInterface.runSQL(sql)
            c, sqlLock = databaseInterface.querySQL(sql)
            row = c.fetchone()
            while row != None:
                ret.append(row)
                row = c.fetchone()
            sqlLock.release()
            break
    if fileName.lower().endswith('.pst'):
        global removeOnceExtracted
        sql = """SELECT CR.pk, CR.command, CR.GroupMember
        FROM CommandRelationships AS CR
        JOIN FileIDs ON CR.fileID=FileIDs.pk
        JOIN CommandClassifications ON CR.commandClassification = CommandClassifications.pk
        WHERE FileIDs.description='A .pst file'
        AND CommandClassifications.classification = 'extract';"""
        c, sqlLock = databaseInterface.querySQL(sql)
        row = c.fetchone()
        while row != None:
            ret.append(row)
            row = c.fetchone()
        sqlLock.release()

    #check if not to remove
    for extension in removeOnceExtractedSkip:
        if fileName.lower().endswith(extension.lower()):
            removeOnceExtracted = False
            break
    return ret

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
    if ext in ['.iso']:
        outputDirectory = replacementDic['%outputDirectory%'] 
        exitCode += main(opts, outputDirectory)
        
    exit(exitCode)

