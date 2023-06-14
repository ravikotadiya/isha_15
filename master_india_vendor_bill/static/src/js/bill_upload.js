odoo.define('master.india.account.bills.tree', function (require) {
"use strict";
    var core = require('web.core');
    var ListController = require('web.ListController');
    var ListView = require('web.ListView');
    var UploadBillMixin = require('account.upload.bill.mixin');
    var viewRegistry = require('web.view_registry');

    var BillsListController = ListController.extend(UploadBillMixin, {
        buttons_template: 'BillsListView.buttons',
        events: _.extend({}, ListController.prototype.events, {
            'click .o_button_upload_bill': '_onUpload',
            'change .o_vendor_bill_upload .o_form_binary_form': '_onAddAttachment',
        }),
        _onFileUploaded: function () {
            // Callback once attachment have been created, create a bill with attachment ids
            debugger;
            var self = this;
            var attachments = Array.prototype.slice.call(arguments, 1);
            // Get id from result
            var attachent_ids = attachments.reduce(function(filtered, record) {
                if (record.id) {
                    filtered.push(record.id);
                }
                return filtered;
            }, []);
            if (this._title == 'Bills'){
                return this._rpc({
                model: 'master.india.instance',
                method: 'get_data_from_attachment',
                args: ["", attachent_ids],
                context: this.initialState.context,
                }).then(function(result) {
                    self.do_action(result);
                }).catch(function () {
                    // Reset the file input, allowing to select again the same file if needed
                    self.$('.o_vendor_bill_upload .o_input_file').val('');
                });
            }
            else{
                return this._rpc({
                model: 'account.journal',
                method: 'create_invoice_from_attachment',
                args: ["", attachent_ids],
                context: this.initialState.context,
                }).then(function(result) {
                    self.do_action(result);
                }).catch(function () {
                    // Reset the file input, allowing to select again the same file if needed
                    self.$('.o_vendor_bill_upload .o_input_file').val('');
                });
            }

        },
    });

    var BillsListView = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Controller: BillsListController,
        }),
    });

    viewRegistry.add('account_tree', BillsListView);
});