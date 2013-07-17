/*
This file is part of Archivematica.

Copyright 2010-2013 Artefactual Systems Inc. <http://artefactual.com>

Archivematica is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Archivematica is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Archivematica.  If not, see <http://www.gnu.org/licenses/>.
*/

function createDirectoryPicker(baseDirectory, modalCssId, targetCssId) {
  var selector = new DirectoryPickerView({
    ajaxChildDataUrl: '/filesystem/children/',
    el: $('#explorer'),
    levelTemplate: $('#template-dir-level').html(),
    entryTemplate: $('#template-dir-entry').html()
  });

  selector.structure = {
    'name': baseDirectory.replace(/\\/g,'/').replace( /.*\//, '' ),      // parse out path basename
    'parent': baseDirectory.replace(/\\/g,'/').replace(/\/[^\/]*$/, ''), // parse out path directory
    'children': []
  };

  selector.options.entryDisplayFilter = function(entry) {
    // if a file and not an archive file or disk image, then hide
    var nornalizedEntry = entry.attributes.name.replace(/^\s+|\s+$/g, '').toLowerCase()
        allowedExtensions = [
          'zip',
          'tgz',
          'tar.gz',
          'e01',
          'iso',
          'dmg',
          'cue',
          'ad1',
          'dsk',
          'bin',
          'raw'
        ],
        hasAllowedExtension = false;

    for (var i = 0; i < allowedExtensions.length; i++) {
      var extension = allowedExtensions[i];
      if (nornalizedEntry.indexOf(extension, nornalizedEntry.length - extension.length) !== -1) {
        hasAllowedExtension = true;
      }
    }

    if (entry.children == undefined && !hasAllowedExtension) {
      return false;
    }
    return true;
  };

  selector.options.actionHandlers = [{
    name: 'Select',
    description: 'Select',
    iconHtml: 'Add',
    logic: function(result) {
      var $transferPathRowEl = $('<div></div>')
        , $transferPathEl = $('<span class="transfer_path"></span>')
        , $transferPathDeleteRl = $('<span style="margin-left: 1em;"><img src="/media/images/delete.png" /></span>');

      $transferPathDeleteRl.click(function() {
        $transferPathRowEl.remove();
      });

      $transferPathEl.html(result.path);
      $transferPathRowEl.append($transferPathEl);
      $transferPathRowEl.append($transferPathDeleteRl);
      $('#' + targetCssId).append($transferPathRowEl);
      $('#' + modalCssId).remove();

      // tiger stripe transfer paths
      $('.transfer_path').each(function() {
        $(this).parent().css('background-color', '');
      });
      $('.transfer_path:odd').each(function() {
        $(this).parent().css('background-color', '#eee');
      });
    }
  }];

  selector.render();
}
