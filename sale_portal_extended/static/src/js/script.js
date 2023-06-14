odoo.define('sale_portal_extended.sales', function (require) {
    'use strict';


    var rpc = require('web.rpc');
    var ajax = require('web.ajax');
    var publicWidget = require('web.public.widget');

    publicWidget.registry.manage_sale = publicWidget.Widget.extend({
        selector: '.o_portal',
        events: {
            'click .create_quote': '_onCreate_quote',
        },
        start: function () {
            return this._super.apply(this, arguments);
        },
        _onCreate_quote: function (ev) {
            $('#createquote').modal('show');
            $(".submit_quote_form").click(function () {
                var form = document.getElementById('quoteform');
                var formData = new FormData(form);
                debugger
                var xhr = new XMLHttpRequest();
                xhr.open('POST', '/create_update_quote', true);

                xhr.onreadystatechange = function () {
                    if (xhr.readyState === XMLHttpRequest.DONE) {
                        if (xhr.status === 200) {
                            // Request succeeded
                            debugger
                            var res = JSON.parse(xhr.responseText)
                            if (res.result == 'error') {
                                $(".status").removeClass('d-none').addClass('d-block')
                                $(".status").html(res.log)
//                                setTimeout(function () {
//                                   location.reload()
//                                }, 5000);

                            } else if (res.result == 'sucess') {
                                $(".status").addClass('d-none').removeClass('d-block')
                                location.reload()
                            }
                        } else {
                            // Request failed
                            console.error('Error: ' + xhr.status);
                        }
                    }
                };

                xhr.send(formData);
            });
            $(".close_quote_form").click(function () {
                $('#createquote').modal('hide');
            });

        }
    });
});
