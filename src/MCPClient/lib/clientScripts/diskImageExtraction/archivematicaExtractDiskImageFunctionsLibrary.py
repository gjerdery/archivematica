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
import os
import sys

def getTSKImages(filePath):
    ret = [filePath]
    """Helps with multipart images. Returns the arguments needed for icat & fiwalk."""
    dir = os.path.dirname(filePath)
    fileName, ext = os.path.splitext(os.path.basename(filePath))
    
    #compare the other files in the directory, and look for multipart
    for file in os.listdir(dir):
        fileName2, ext2 = os.path.splitext(filePath)
        if ext2.lower() in [".txt", ".xml", ".csv", ".rtf", ".xml"]:
            continue
        if fileName2 != fileName:
            continue
        ret.append(os.path.join(dir, file))
    return '" "'.join(ret)
        
    