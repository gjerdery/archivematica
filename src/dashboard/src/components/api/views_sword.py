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

import cPickle
import datetime
import os
import gearman
import json
import shutil
import tempfile
import threading
import time
import uuid
from lxml import etree as etree
from django.http import HttpResponse
from django.db import transaction
from django.template.loader import render_to_string
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.shortcuts import render
from main import models
from components import helpers
from components.api.views import approve_transfer_via_mcp
import sys
sys.path.append("/usr/lib/archivematica/archivematicaCommon")
import databaseInterface

def _transfer_storage_path(uuid):
    transfer = models.Transfer.objects.get(uuid=uuid)
    return transfer.currentlocation

def _transfer_storage_path_root():
    return os.path.join(
            helpers.get_server_config_value('sharedDirectory'),
            'staging'
    )

def _create_transfer_directory_and_db_entry(transfer_specification):
    transfer_uuid = uuid.uuid4().__str__()

    if 'name' in transfer_specification:
        transfer_name = transfer_specification['name']
    else:
        transfer_name = 'Untitled'

    transfer_path = os.path.join(
        _transfer_storage_path_root(),
        transfer_name
    )

    transfer_path = helpers.pad_destination_filepath_if_it_already_exists(transfer_path)
    os.mkdir(transfer_path)
    os.chmod(transfer_path, 02770) # drwxrws---

    if os.path.exists(transfer_path):
        transfer = models.Transfer.objects.create(
            uuid=transfer_uuid,
            currentlocation=transfer_path
        )

        if 'sourceofacquisition' in transfer_specification:
            transfer.sourceofacquisition = transfer_specification['sourceofacquisition']

        transfer.save()
        return transfer_uuid

def _transfer_list():
    transfer_list = []
    transfers = models.Transfer.objects.filter(currentlocation__startswith=_transfer_storage_path_root())
    for transfer in transfers:
        transfer_list.append(transfer.uuid)
    return transfer_list

def _sword_error_response(request, error_details):
    error_details['request'] = request
    error_details['update_time'] = datetime.datetime.now().__str__()
    error_details['user_agent'] = request.META['HTTP_USER_AGENT']
    error_xml = render_to_string('api/sword/error.xml', error_details)
    return HttpResponse(error_xml, status=error_details['status'])

def _write_file_from_request_body(request, file_path):
    bytes_written = 0
    new_file = open(file_path, 'ab')
    chunk = request.read()
    if chunk != None:
        new_file.write(chunk)
        bytes_written += len(chunk)
        chunk = request.read()
    new_file.close()
    return bytes_written

def _handle_upload_request(request, uuid, replace_file=False):
    error = None
    bad_request = None

    if 'HTTP_CONTENT_DISPOSITION' in request.META:
        filename = request.META['HTTP_CONTENT_DISPOSITION']

        # TODO: fix temporary hack
        # TODO: handle malformed header
        filename = filename.replace('attachment; filename=', '')

        if filename != '':
            file_path = os.path.join(_transfer_storage_path(uuid), filename)

            if replace_file:
                # if doing a file replace, the file being replaced must exist
                if os.path.exists(file_path):
                    os.remove(file_path)
                    bytes_written = _write_file_from_request_body(request, file_path)
                else:
                    bad_request = 'File does not exist.'
            else:
                bytes_written = _write_file_from_request_body(request, file_path)

            # TODO: better response
            return HttpResponse('Wrote ' + str(bytes_written))
        else:
            bad_request = 'No filename found in Content-disposition header.'
    else:
        bad_request = 'Content-disposition must be set in request header.'

    if bad_request != None:
        error = {
            'summary': bad_request,
            'status': 400
        }

    if error != None:
        return _sword_error_response(request, error)

@transaction.commit_manually
def _flush_transaction():
    transaction.commit()

def _fetch_content(transfer_uuid, object_content_urls):
    # write resources to temp file
    temp_dir = tempfile.mkdtemp()
    os.chmod(temp_dir, 02770) # drwxrws---
    resource_list_filename = os.path.join(temp_dir, 'resource_list.txt')
    with open(resource_list_filename, 'w') as resource_list_file:
        for url in object_content_urls:
            resource_list_file.write(url + "\n")

    # create job record to associate tasks with the transfer
    now = datetime.datetime.now()
    job_uuid = uuid.uuid4().__str__()
    job = models.Job()
    job.jobuuid = job_uuid
    job.sipuuid = transfer_uuid
    job.createdtime = now.__str__()
    job.createdtimedec = int(now.strftime("%s"))
    job.hidden = True
    job.save()

    # create task record so progress can be tracked
    task_uuid = uuid.uuid4().__str__()
    arguments = '"' + resource_list_filename + '" "' + _transfer_storage_path(transfer_uuid) + '"'

    # create task record so time can be tracked by the MCP client
    # ...Django doesn't like putting 0 in datetime fields
    # TODO: put in arguments, etc. and use proper sanitization
    sql = "INSERT INTO Tasks (taskUUID, jobUUID, startTime) VALUES ('" + task_uuid + "', '" + job_uuid + "', 0)"
    databaseInterface.runSQL(sql)
    _flush_transaction() # refresh ORM after manual SQL

    # submit job to gearman
    gm_client = gearman.GearmanClient(['localhost:4730'])
    data = {'createdDate' : datetime.datetime.now().__str__()}
    data['arguments'] = arguments
    result = gm_client.submit_job(
        'fetchfedoracommonsobjectcontent_v0.0',
        cPickle.dumps(data),
        task_uuid
    )

    # record task completion time
    task = models.Task.objects.get(taskuuid=task_uuid)
    task.endtime = datetime.datetime.now().__str__() # TODO: endtime seems weird... Django time zone issue?
    task.save()

    # delete temp dir
    shutil.rmtree(temp_dir)

def service_document(request):
    service_document_xml = render_to_string('api/sword/service_document.xml')
    return HttpResponse(service_document_xml)

"""
Example GET of transfers list:

  curl -v http://127.0.0.1/api/v2/transfer

Example POST creation of transfer:

  curl -v -H "In-Progress: true" -d "some METS XML" --request POST http://localhost/api/v2/transfer
"""
# TODO: add authentication
# TODO: error is transfer completed, but has no files?
def transfer_collection(request):
    error = None
    bad_request = None

    if request.method == 'GET':
        # return list of transfers as ATOM feed
        feed = {
            'title': 'Transfers',
            'url': reverse('components.api.views_sword.transfer_collection')
        }

        items = []
        for uuid in _transfer_list():
            transfer = models.Transfer.objects.get(uuid=uuid)
            items.append({
                'title': os.path.basename(transfer.currentlocation),
                'url': reverse('components.api.views_sword.transfer', args=[uuid])
            })

        collection_xml = render_to_string('api/sword/collection.xml', locals())
        return HttpResponse(collection_xml)
    elif request.method == 'POST':
        # is the transfer still in progress
        if 'HTTP_IN_PROGRESS' in request.META and request.META['HTTP_IN_PROGRESS'] == 'true':
            # process creation request, if criteria met
            if request.body != '':
                try:
                    # write request body to temp file
                    filehandle, temp_filepath = tempfile.mkstemp()
                    _write_file_from_request_body(request, temp_filepath)

                    # parse XML
                    try:
                        tree = etree.parse(temp_filepath)
                        root = tree.getroot()
                        transfer_name = root.find("{http://www.w3.org/2005/Atom}title").text

                        # assemble transfer specification
                        transfer_specification = {}
                        transfer_specification['name'] = transfer_name
                        if 'HTTP_ON_BEHALF_OF' in request.META:
                            transfer_specification['sourceofacquisition'] = request.META['HTTP_ON_BEHALF_OF']

                        transfer_uuid = _create_transfer_directory_and_db_entry(transfer_specification)

                        if transfer_uuid != None:
                            # TODO: parse XML and start fetching jobs if needed
                            mock_object_content_urls = [
                                'http://192.168.1.231:8080/fedora/objects/hat:man/datastreams/rickpic/content'
                            ]

                            # create thread so content URLs can be downloaded asynchronously
                            thread = threading.Thread(target=_fetch_content, args=(transfer_uuid, mock_object_content_urls))
                            thread.start()

                            # respond with SWORD 2.0 deposit receipt XML
                            receipt_xml = render_to_string('api/sword/deposit_receipt.xml', {'transfer_uuid': transfer_uuid})
                            response = HttpResponse(receipt_xml, mimetype='text/xml', status=201)
                            response['Location'] = transfer_uuid
                            return response # Created
                        else:
                            error = {
                                'summary': 'Could not create transfer: contact an administrator.',
                                'status': 500
                        }
                    except etree.XMLSyntaxError:
                        bad_request = 'Error parsing XML.'
                except Exception as e:
                    return HttpResponse(str(e))
                    bad_request = 'Error writing temp file.'
            else:
                bad_request = 'A request body must be sent when creating a transfer.'
        else:
            bad_request = 'The In-Progress header must be set to true when creating a transfer.'
    else:
        error = {
            'summary': 'This endpoint only responds to the GET and POST HTTP methods.',
            'status': 405
        }

    if bad_request != None:
        error = {
            'summary': bad_request,
            'status': 400
        }

    if error != None:
        return _sword_error_response(request, error)

"""
Example POST finalization of transfer:

  curl -v -H "In-Progress: false" --request POST http://localhost/api/v2/transfer/5bdf83cd-5858-4152-90e2-c2426e90e7c0

Example DELETE if transfer:

  curl -v -XDELETE http://localhost/api/v2/transfer/5bdf83cd-5858-4152-90e2-c2426e90e7c0
"""
# TODO: add authentication
def transfer(request, uuid):
    error = None
    bad_request = None

    if request.method == 'GET':
        # details about a transfer
        return HttpResponse('Some detail XML')
    elif request.method == 'POST':
        # is the transfer ready to move to a processing directory?
        if 'HTTP_IN_PROGRESS' in request.META and request.META['HTTP_IN_PROGRESS'] == 'false':
            # TODO: check that related task is complete before copying
            # ...task row must exist and task endtime must be equal to or greater than start time
            try:
                transfer = models.Transfer.objects.get(uuid=uuid)

                if transfer.magiclink == None:
                    if len(os.listdir(transfer.currentlocation)) > 0:
                        helpers.copy_to_start_transfer(transfer.currentlocation, 'standard', {'uuid': uuid})

                        # wait for watch directory to determine a transfer is awaiting
                        # approval then attempt to approve it
                        time.sleep(5)
                        approve_transfer_via_mcp(
                            os.path.basename(transfer.currentlocation),
                            'standard',
                        1
                        ) # TODO: replace hardcoded user ID

                        return HttpResponse('Transfer finalized and approved.')
                    else:
                        bad_request = 'This transfer contains no files.'
                else:
                    bad_request = 'This transfer has already been started and approved.'
            except ObjectDoesNotExist:
                error = {
                    'summary': 'This transfer could not be found.',
                    'status': 404
                }
        else:
            bad_request = 'The In-Progress header must be set to false when starting transfer processing.'
    elif request.method == 'PUT':
        # update transfer and return details
        return HttpResponse('Transfer updated.')
    elif request.method == 'DELETE':
        # delete transfer files
        transfer_path = _transfer_storage_path(uuid)
        shutil.rmtree(transfer_path)

        # delete entry in Transfers table (and task?)
        transfer = models.Transfer.objects.get(uuid=uuid)
        transfer.delete()
        return HttpResponse('Transfer deleted.')
    else:
        error = {
            'summary': 'This endpoint only responds to the GET, POST, PUT, and DELETE HTTP methods.',
            'status': 405
        }

    if bad_request != None:
        error = {
            'summary': bad_request,
            'status': 400
        }

    if error != None:
                return _sword_error_response(request, error)

"""
Example GET of files list:

  curl -v http://127.0.0.1/api/v2/transfer/03ce11a5-32c1-445a-83ac-400008894f78/media/

Example POST of file:

  curl -v -H "Content-Disposition: attachment; filename=joke.jpg" --request POST \
    --data-binary "@joke.jpg" \
    http://localhost/api/v2/transfer/03ce11a5-32c1-445a-83ac-400008894f78/media

Example DELETE of file:

  curl -v -XDELETE \
    "http://localhost/api/v2/transfer/03ce11a5-32c1-445a-83ac-400008894f78/media?filename=thing.jpg"
"""
# TODO: implement Content-MD5 header so we can verify file upload was successful
# TODO: better Content-Disposition header parsing
# TODO: add authentication
def transfer_files(request, uuid):
    error = None

    if request.method == 'GET':
        transfer_path = _transfer_storage_path(uuid)
        if os.path.exists(transfer_path):
            return helpers.json_response(os.listdir(transfer_path))
        else:
            error = {
                'summary': 'This transfer path does not exist.',
                'status': 404
            }
    elif request.method == 'PUT':
        # replace a file in the transfer
        return _handle_upload_request(request, uuid, True)
    elif request.method == 'POST':
        # add a file to the transfer
        return _handle_upload_request(request, uuid)
    elif request.method == 'DELETE':
        filename = request.GET.get('filename', '')
        if filename != '':
            transfer_path = _transfer_storage_path(uuid)
            file_path = os.path.join(transfer_path, filename) 
            if os.path.exists(file_path):
                os.remove(file_path)
                return HttpResponse('Deleted.')
            else:
                error = {
                    'summary': 'The transfer path does not exist.',
                    'status': 404
                }
        else:
            error = {
                'summary': 'No filename specified.',
                'status': 400
            }
    else:
        error = {
            'summary': 'This endpoint only responds to the GET, POST, PUT, and DELETE HTTP methods.',
            'status': 405
        }

    if error != none:
                return _sword_error_response(request, error)

# TODO: add authentication
def transfer_state(request, uuid):
    error = None

    if request.method == 'GET':
        events = []

        # get transfer creation job, if any
        job = None
        try:
            job = models.Job.objects.filter(sipuuid=uuid, hidden=True)[0]
        except:
            error = {
                'summary': 'Job not found. Contact an administrator.',
                'status': 404
            }

        task = None
        if job != None:
            try:
                task = models.Task.objects.filter(job=job)[0]
            except:
                pass

        if task != None:
            task_state = 'In progress'

            if task.endtime != '':
                task_state = 'Complete'

            events.append({
                "type":   "Creating transfer",
                "status": task_state
            })

        return HttpResponse(events)
    else:
        error = {
            'summary': 'This endpoint only responds to the GET HTTP method.',
            'status': 405
        }

    if error != none:
                return _sword_error_response(request, error)
