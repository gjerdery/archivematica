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

import os
import shutil
import sys
import urllib2
import tempfile

def download_resources_listed_in_file(file_containing_urls, destination_directory):
    download_counter = 1
    temp_dir = tempfile.mkdtemp()

    # download each resource in file containing URLs
    urls = open(file_containing_urls)

    for url in urls:
        # down resource to a temporary file
        temp_filepath = os.path.join(temp_dir, str(download_counter))
        response = download_resource(url, temp_filepath)

        # move to destination_directory
        destination_filepath = os.path.join(destination_directory, _filename_from_response(response))
        shutil.move(temp_filepath, destination_filepath)
        download_counter += 1
    urls.close()

    # cleanup
    os.rmdir(temp_dir)

def _filename_from_response(response):
    info = response.info()
    return _parse_filename_from_content_disposition(info['content-disposition'])

def _parse_filename_from_content_disposition(content_disposition):
    filename_start = content_disposition.index('filename="') + 10
    return content_disposition[filename_start:-1]

def download_resource(url, filepath):
    request = urllib2.urlopen(url)
    buffer = 16 * 1024
    with open(filepath, 'wb') as fp:
        while True:
            chunk = request.read(buffer)
            if not chunk: break
            fp.write(chunk)
    return request

if __name__ == '__main__':
    print 'Downloading started.'
    file_containing_urls = sys.argv[1]
    destination_directory = sys.argv[2]

    download_resources_listed_in_file(file_containing_urls, destination_directory)
    print 'Downloading complete.'
