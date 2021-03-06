// leave at least 2 line with only a star on it below, or doc generation fails
/**
 *
 *
 * Placeholder for custom user javascript
 * mainly to be overridden in profile/static/custom/custom.js
 * This will always be an empty file in IPython
 *
 * User could add any javascript in the `profile/static/custom/custom.js` file.
 * It will be executed by the ipython notebook at load time.
 *
 * Same thing with `profile/static/custom/custom.css` to inject custom css into the notebook.
 *
 *
 * The object available at load time depend on the version of IPython in use.
 * there is no guaranties of API stability.
 *
 * The example below explain the principle, and might not be valid.
 *
 * Instances are created after the loading of this file and might need to be accessed using events:
 *     define([
 *        'base/js/namespace',
 *        'base/js/events'
 *     ], function(IPython, events) {
 *         events.on("app_initialized.NotebookApp", function () {
 *             IPython.keyboard_manager....
 *         });
 *     });
 *
 * __Example 1:__
 *
 * Create a custom button in toolbar that execute `%qtconsole` in kernel
 * and hence open a qtconsole attached to the same kernel as the current notebook
 *
 *    define([
 *        'base/js/namespace',
 *        'base/js/events'
 *    ], function(IPython, events) {
 *        events.on('app_initialized.NotebookApp', function(){
 *            IPython.toolbar.add_buttons_group([
 *                {
 *                    'label'   : 'run qtconsole',
 *                    'icon'    : 'icon-terminal', // select your icon from http://fortawesome.github.io/Font-Awesome/icons
 *                    'callback': function () {
 *                        IPython.notebook.kernel.execute('%qtconsole')
 *                    }
 *                }
 *                // add more button here if needed.
 *                ]);
 *        });
 *    });
 *
 * __Example 2:__
 *
 * At the completion of the dashboard loading, load an unofficial javascript extension
 * that is installed in profile/static/custom/
 *
 *    define([
 *        'base/js/events'
 *    ], function(events) {
 *        events.on('app_initialized.DashboardApp', function(){
 *            require(['custom/unofficial_extension.js'])
 *        });
 *    });
 *
 * __Example 3:__
 *
 *  Use `jQuery.getScript(url [, success(script, textStatus, jqXHR)] );`
 *  to load custom script into the notebook.
 *
 *    // to load the metadata ui extension example.
 *    $.getScript('/static/notebook/js/celltoolbarpresets/example.js');
 *    // or
 *    // to load the metadata ui extension to control slideshow mode / reveal js for nbconvert
 *    $.getScript('/static/notebook/js/celltoolbarpresets/slideshow.js');
 *
 *
 * @module IPython
 * @namespace IPython
 * @class customjs
 * @static
 */

function prependERP5Help() {
  var kernelname = Jupyter.notebook.kernel_selector.current_selection;
  var display_text = "<div class='output_subarea output_text output_result'>\
    <pre>Follow these steps to customize your notebook with ERP5 kernel :-</br>\
    1. Make sure you have 'erp5_data_notebook' business template installed in your ERP5</br>\
    2. <b>%erp5_url &lt;your_erp5_url&gt;/Base_executeJupyter</b></br>\
    3. <b>%erp5_user &lt;your_erp5_username&gt;</b></br>\
    4. <b>%erp5_password &lt;your_erp5_password&gt;</b></br>\
    5. <b>%notebook_set_reference &lt;your_notebook_reference&gt;</b></br>\
    It would be better to set the reference to match with erp5 reference pattern.</br>\
    6. As soon as you see 'Please Proceed' message you can now access your erp5 using notebook.</br>\
    <p><u>OTHER USEFUL MAGICS</u> -</br>\
    <b>%my_notebooks</b> -This is used to display all the notebooks created by the specific user.</br>\
    <b>%notebook_set_title</b> -This sets the title of the current notebook.</br>\
    NOTE: Do not dynamically alter imported module objects as they are not being saved in DB, </br>\
    so changes to them would be disregarded and would throw an error.</br>\
    <p><u>About classes, functions and global state on modules:</u></p>\
    Your code is going to be executed by ERP5, which can have many nodes </br>\
    and there is no guarantee that your code is always going to be executed by the same server.</br>\
    This means that objects which cannot be stored in the ZODB, like functions, classes and modules </br>\
    won't be available across nodes. To solve this issue, you need to use a special object </br>\
    called 'environment' to store your global setup. This object was designed to hold global </br>\
    state and restore it for each code cell. Example:</br></br>\
    <b>def my_setup():</br>\
      # import modules, define functions and classes</br>\
      # and set global state on modules</br>\
      # return dict of variables to be available in code cells</br>\
      {'my_var': 1}</br>\
    environment.define(my_setup, 'my custom setup')</b></br></br>\
    After you execute this cell, the <b>my_setup</b> function will run before each of the</br>\
    following cells and the <b>my_var</b> variable will be created and set to 1.</br></br>\
    <b>WARNING:</b> it is not recommended to have too many setup functions in the environment, </br>\
    because they will be executed in every code cell and can cause a substantial slow down.\
    </pre></div>";

    if (kernelname=="erp5"){
      $('div#notebook-container').prepend(display_text);
    }
}

define([
  'base/js/namespace',
  'base/js/promises'
], function(Jupyter, promises) {
  promises.notebook_loaded.then(function() {
    prependERP5Help();
  });
});
