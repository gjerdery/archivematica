$(document).ready(function() {
  var ajaxChildDataUrl = '/filesystem/children/'
    , ajaxSelectedDirectoryUrl = '/administration/sources/json/'
    , ajaxAddDirectoryUrl = '/administration/sources/json/'
    , ajaxDeleteDirectoryUrl = '/administration/sources/delete/json/'
    , picker = new DirectoryPickerView({
      el:               $('#explorer'),
      levelTemplate:    $('#template-dir-level').html(),
      entryTemplate:    $('#template-dir-entry').html(),
      ajaxChildDataUrl: ajaxChildDataUrl,
      ajaxSelectedDirectoryUrl: ajaxSelectedDirectoryUrl,
      ajaxAddDirectoryUrl: ajaxAddDirectoryUrl,
      ajaxDeleteDirectoryUrl: ajaxDeleteDirectoryUrl
  });

  picker.structure = {
    'name': 'home',
    'parent': '',
    'children': []
  };

  picker.render();
  picker.updateSelectedDirectories();
});
