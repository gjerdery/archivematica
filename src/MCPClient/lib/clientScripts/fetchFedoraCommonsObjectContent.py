#!/usr/bin/python -OO

# This file is part of Archivematica.
#
# Copyright 2010-2012 Artefactual Systems Inc. <http://artefactual.com>
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
# @author Mike Cantelon <mike@artefactual.com>

import sys
import urllib2

def download_resorces_listed_in_file(file_containing_urls, destination_directory):
    urls = open(file_containing_urls, 'r')
    for url in urls:
        # TODO: change destination_directory into a file
        download_resource(url, destination_directory)
    urls.close()

def download_resource(url, filepath):
    request = urllib2.urlopen(url)
    buffer = 16 * 1024
    with open(filepath, 'wb') as fp:
        while True:
            chunk = req.read(buffer)
            if not chunk: break
            fp.write(chunk)

if __name__ == '__main__':
    file_containing_urls = sys.argv[1]
    destination_directory = sys.argv[2]
    download_resorces_listed_in_file(file_containing_urls, destination_directory)
