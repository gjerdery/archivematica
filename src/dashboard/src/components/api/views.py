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
import uuid
from django.http import Http404, HttpResponse, HttpResponseForbidden, HttpResponseServerError
from django.db.models import Q
from django.template.loader import render_to_string
from tastypie.authentication import ApiKeyAuthentication
from contrib.mcp.client import MCPClient
from main import models
from components import helpers

def authenticate_request(request):
    error = None

    api_auth = ApiKeyAuthentication()
    authorized = api_auth.is_authenticated(request)

    if authorized == True:
        client_ip = request.META['REMOTE_ADDR']
        whitelist = helpers.get_setting('api_whitelist', '127.0.0.1').split("\r\n")
        try:
            whitelist.index(client_ip)
            return
        except:
            error = 'Host/IP ' + client_ip + ' not authorized.'
    else:
        error = 'API key not valid.'

    return error

#
# Example: http://127.0.0.1/api/transfer/unapproved?username=mike&api_key=<API key>
#
def unapproved_transfers(request):
    if request.method == 'GET':
        auth_error = authenticate_request(request)

        response = {}

        if auth_error == None:
            message    = ''
            error      = None
            unapproved = []

            jobs = models.Job.objects.filter(
                 (
                     Q(jobtype="Approve standard transfer")
                     | Q(jobtype="Approve DSpace transfer")
                     | Q(jobtype="Approve bagit transfer")
                     | Q(jobtype="Approve zipped bagit transfer")
                 ) & Q(currentstep='Awaiting decision')
            )

            for job in jobs:
                # remove standard transfer path from directory (and last character)
                type_and_directory = job.directory.replace(
                    get_modified_standard_transfer_path() + '/',
                    '',
                    1
                )

                # remove trailing slash if not a zipped bag file
                if not helpers.file_is_an_archive(job.directory):
                    type_and_directory = type_and_directory[:-1]

                transfer_watch_directory = type_and_directory.split('/')[0]
                transfer_type = helpers.transfer_type_by_directory(transfer_watch_directory)

                job_directory = type_and_directory.replace(transfer_watch_directory + '/', '', 1)

                unapproved.append({
                    'type':      transfer_type,
                    'directory': job_directory
                })

            # get list of unapproved transfers
            # return list as JSON
            response['results'] = unapproved

            if error != None:
                response['message'] = error
                response['error']   = True
            else:
                response['message'] = 'Fetched unapproved transfers successfully.'

                if error != None:
                    return HttpResponseServerError(
                        json.dumps(response),
                        mimetype='application/json'
                    )
                else:
                    return helpers.json_response(response)
        else:
            response['message'] = auth_error
            response['error']   = True 
            return HttpResponseForbidden(
                json.dumps(response),
                mimetype='application/json'
            )
    else:
        return Http404

#
# Example: curl --data \
#   "username=mike&api_key=<API key>&directory=MyTransfer" \
#   http://127.0.0.1/api/transfer/approve
#
def approve_transfer(request):
    if request.method == 'POST':
        auth_error = authenticate_request(request)

        response = {}

        if auth_error == None:
            message = ''
            error   = None

            directory = request.POST.get('directory', '')
            type      = request.POST.get('type', 'standard')
            error     = approve_transfer_via_mcp(directory, type, request.user.id)

            if error != None:
                response['message'] = error
                response['error']   = True
            else:
                response['message'] = 'Approval successful.'

            if error != None:
                return HttpResponseServerError(
                    json.dumps(response),
                    mimetype='application/json'
                )
            else:
                return helpers.json_response(response)
        else:
            response['message'] = auth_error
            response['error']   = True
            return HttpResponseForbidden(
                json.dumps(response),
                mimetype='application/json'
            )
    else:
        raise Http404

def get_modified_standard_transfer_path(type=None):
    path = os.path.join(
        helpers.get_server_config_value('watchDirectoryPath'),
        'activeTransfers'
    )

    if type != None:
        try:
            path = os.path.join(path, helpers.transfer_directory_by_type(type))
        except:
            return None

    shared_directory_path = helpers.get_server_config_value('sharedDirectory')
    return path.replace(shared_directory_path, '%sharedPath%', 1)

def approve_transfer_via_mcp(directory, type, user_id):
    error = None

    if (directory != ''):
        # assemble transfer path
        modified_transfer_path = get_modified_standard_transfer_path(type)

        if modified_transfer_path == None:
            error = 'Invalid transfer type.'
        else:
            if type == 'zipped bag':
                transfer_path = os.path.join(modified_transfer_path, directory)
            else:
                transfer_path = os.path.join(modified_transfer_path, directory) + '/'

            # look up job UUID using transfer path
            try:
                job = models.Job.objects.filter(directory=transfer_path, currentstep='Awaiting decision')[0]

                type_task_config_descriptions = {
                    'standard':     'Approve standard transfer',
                    'unzipped bag': 'Approve bagit transfer',
                    'zipped bag':   'Approve zipped bagit transfer',
                    'dspace':       'Approve DSpace transfer',
                    'maildir':      'Approve maildir transfer',
                    'TRIM':         'Approve TRIM transfer'
                }

                type_description = type_task_config_descriptions[type]

                # use transfer type to fetch possible choices to execute
                task = models.TaskConfig.objects.get(description=type_description)
                link = models.MicroServiceChainLink.objects.get(currenttask=task.pk)
                choices = models.MicroServiceChainChoice.objects.filter(choiceavailableatlink=link.pk)

                # attempt to find appropriate choice
                chain_to_execute = None
                for choice in choices:
                    chain = models.MicroServiceChain.objects.get(pk=choice.chainavailable)
                    if chain.description == 'Approve transfer':
                        chain_to_execute=chain.pk

                # execute choice if found
                if chain_to_execute != None:
                    client = MCPClient()

                    result = client.execute(job.pk, chain_to_execute, user_id)
                else:
                    error = 'Error: could not find MCP choice to execute.'

            except:
                error = 'Unable to find unapproved transfer directory.'

    else:
        error = 'Please specify a transfer directory.'

    return error

def _transfer_storage_path(uuid=None):
    shared_directory_path = helpers.get_server_config_value('sharedDirectory')

    storage_path = os.path.join(
        shared_directory_path,
        'www/AIPsStore/transferBacklog/originals'
    )

    if uuid == None:
        return storage_path
    else:
        return os.path.join(storage_path, uuid)

def _create_transfer_directory_and_db_entry(transfer_specification):
    transfer_uuid = uuid.uuid4().__str__()

    transfer_path = os.path.join(
        _transfer_storage_path(),
        transfer_uuid
    )

    os.mkdir(transfer_path)

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
    transfers = models.Transfer.objects.filter(currentlocation__startswith=_transfer_storage_path())
    for transfer in transfers:
        transfer_list.append(transfer.uuid)
    return transfer_list

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

"""
Example GET of transfers list:

  curl -v http://127.0.0.1/api/v2/transfer/

Example POST creation of transfer:

  curl -v -d "some METS XML" --request POST http://localhost/api/v2/transfer/

Example POST finalization of transfer:

  curl -v -H "In-Progress: false" --request POST http://localhost/api/v2/transfer/
"""
# TODO: add authentication
# TODO: error is transfer completed, but has no files?
def create_or_list_transfers(request):
    if request.method == 'GET':
        # return list of transfers
        return helpers.json_response(_transfer_list())
    elif request.method == 'POST':
        # is the transfer ready to move to a processing directory?
        if 'HTTP_IN_PROGRESS' in request.META and request.META['HTTP_IN_PROGRESS'] == 'false':
            # TODO: start a background job to wait until all related jobs are done then move the
            # transfer files into the appropriate watch directory
            #
            #   fetch transfer using ID
            #   transfer = models.Transfer.objects.get(uuid=)
            #   shutil.move(transfer.currentlocation, standard_transfers_directory)
            return HttpResponse('')
        else:
            # process creation request, if criteria met
            if request.body != '':
                transfer_specification = {}
                if 'HTTP_ON_BEHALF_OF' in request.META:
                    transfer_specification['sourceofacquisition'] = request.META['HTTP_ON_BEHALF_OF']
                transfer_uuid = _create_transfer_directory_and_db_entry(transfer_specification)

                # TODO: parse XML and start fetching jobs if needed
                mock_object_content_urls = [
                  'http://127.0.0.1:8080/fedora/objects/people:rick/datastreams/rick_pic/content'
                ]

                # write resources to temp file
                temp_dir = tempfile.mkdtemp()
                resource_list_filename = os.path.join(temp_dir, 'resource_list.txt')
                with open(resource_list_filename, 'w') as resource_list_file:
                    for url in mock_object_content_urls:
                        resource_list_file.write(url + "\n")

                return HttpResponse(resource_list_filename + ' ' + _transfer_storage_path(transfer_uuid))
                # submit download job
                gm_client = gearman.GearmanClient(['localhost:4730'])
                data = {'createdDate' : datetime.datetime.now().__str__()}
                data['arguments'] = resource_list_filename + ' "' + _transfer_storage_path(transfer_uuid) + '"'
                result = gm_client.submit_job('fetchFedoraCommonsObjectContent_v0.0', cPickle.dumps(data), '1145')

                if transfer_uuid != None:
                    receipt_xml = render_to_string('api/transfer_finalized.xml', {'transfer_uuid': transfer_uuid})
                    response = HttpResponse(receipt_xml, mimetype='text/xml', status=201)
                    response['Location'] = transfer_uuid
                    return response # Created
                else:
                    return HttpResponse(status=500) # Server error
            else:
                return HttpResponse(status=400) # Bad request
    else:
        return HttpResponse(status=405) # Method not allowed

# TODO: add authentication
def transfer(request, uuid):
    if request.method == 'GET':
        # details about a transfer
        return HttpResponse('')
    elif request.method == 'PUT':
        # update transfer and return details
        return HttpResponse('')
    elif request.method == 'DELETE':
        # delete transfer
        return HttpResponse('')
    else:
        # return HTTP 405, method not allowed
        return HttpResponse(status=405)

"""
Example GET of files list:

  curl -v http://127.0.0.1/api/v2/transfer/03ce11a5-32c1-445a-83ac-400008894f78/media/

Example POST of file:

  curl -v -d "filename=thing.jpg" --request POST --data-binary "@joke.jpg" \
    http://localhost/api/v2/transfer/03ce11a5-32c1-445a-83ac-400008894f78/media/

Example DELETE of file:

  curl -v -XDELETE \
    "http://localhost/api/v2/transfer/03ce11a5-32c1-445a-83ac-400008894f78/media/?filename=thing.jpg"
"""
# TODO: implement Content-MD5 header so we can verify file upload was successful
# TODO: replace use of "filename" params with Content-Disposition for POST, example: Content-Disposition: attachment; filename=[filename]
# TODO: add authentication
def transfer_files(request, uuid):
    if request.method == 'GET':
        transfer_path = _transfer_storage_path(uuid)
        if os.path.exists(transfer_path):
            return helpers.json_response(os.listdir(transfer_path))
        else:
            return HttpResponse(status=404) # Not found
    elif request.method == 'POST':
        # add a file to the transfer
        # file is in body
        filename = request.POST.get('filename')
        if filename != '':
            file_path = os.path.join(_transfer_storage_path(uuid), filename)
            bytes_written = _write_file_from_request_body(request, file_path)
            return HttpResponse('Wrote ' + str(bytes_written))
        else:
            return HttpResponse(status=400) # Bad request
    elif request.method == 'DELETE':
        filename = request.GET.get('filename', '')
        if filename != '':
            transfer_path = _transfer_storage_path(uuid)
            file_path = os.path.join(transfer_path, filename) 
            if os.path.exists(file_path):
                os.remove(file_path)
                return HttpResponse('Deleted.')
            else:
                return HttpResponse(status=404) # Not found
        else:
            return HttpResponse(status=400) # Bad request
    else:
        return HttpResponse(status=405) # Method not allowed

# TODO: add authentication
def transfer_state(request, uuid):
    if request.method == 'GET':
        # details about a transfer's state
        return HttpResponse('')
    else:
        # return HTTP 405, method not allowed
        return HttpResponse(status=405)
