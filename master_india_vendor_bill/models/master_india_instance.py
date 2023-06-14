import logging
import base64
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
ACCURACY_FIELD = ['invoice_date','supplier_gstin','supplier_name','pan_number','total_tax_amount','invoice_amount','discount','supplier_email']
FIELD_VALUE = ['Invoice Date', 'GST','Name', 'Pan Number','Total Tax Amount','Invoice Amount','Discount','Email']
class MasterIndiaInstance(models.Model):
    _inherit = "master.india.instance"

    def get_file_data(self, file_path):
        # res = super(MasterIndiaInstance, self).get_file_data(file_path)
        res = {'status': True, 'message': 'Data Extracted Successfully! and Data Purge is False', 'data': [
            {'invoice_number': {'value': 'INV/2018/0057', 'accuracy': 89.89}, 'po_number': {'value': '', 'accuracy': 0},
             'invoice_date': {'value': '09/17/2018', 'accuracy': 90.29},
             'invoice_due_date': {'value': '30-09-2018', 'accuracy': 88.23},
             'payment_terms': {'value': '', 'accuracy': 0}, 'irn': {'value': '', 'accuracy': 0},
             'ewaybill_number': {'value': '', 'accuracy': 0},
             'supplier_gstin': {'value': '24AAHCB6536E1ZV', 'accuracy': 74.21},
             'supplier_name': {'value': 'Azure Interior Solutions Private Limited', 'accuracy': 90.73},
             'pan_number': {'value': 'BE0477.472.701', 'accuracy': 99.9}, 'buyer_gstin': {'value': '', 'accuracy': 0},
             'buyer_name': {'value': 'Odoo SA', 'accuracy': 78.73}, 'buyer_pan_number': {'value': '', 'accuracy': 0},
             'ship_to_gstin': {'value': '', 'accuracy': 0}, 'total_taxable': {'value': 541.1, 'accuracy': 99.86},
             'total_igst': {'value': '', 'accuracy': 0}, 'total_cgst': {'value': '', 'accuracy': 0},
             'total_sgst': {'value': '', 'accuracy': 0}, 'total_cess': {'value': '', 'accuracy': 0},
             'total_tax_amount': {'value': '', 'accuracy': 0}, 'invoice_amount': {'value': 541.1, 'accuracy': 80.86},
             'other_charges': {'value': '', 'accuracy': 0}, 'discount': {'value': '', 'accuracy': 0},
             'bank_name': {'value': 'Kotak Mahidra Bank', 'accuracy': 56.29},
             'account_number': {'value': '6912130859', 'accuracy': 99.69},
             'ifsc_code': {'value': 'KKBK0003551', 'accuracy': 61.91}, 'branch': {'value': '', 'accuracy': 0},
             'supplier_address': {'value': ' A405 Pushp Business Campus Ahmedabad, Gujarat, 382418', 'accuracy': 91.06},
             'buyer_address': {'value': ' Chaussée de Namur 40 Grand-Rosière 1367 Belgium', 'accuracy': 83.51},
             'shipping_address': {'value': '', 'accuracy': 0},
             'supplier_email': {'value': 'info@azureinterior.com', 'accuracy': 86.75},
             'qr_supplier_gstin': {'value': '', 'accuracy': 0}, 'qr_buyer_gstin': {'value': '', 'accuracy': 0},
             'qr_invoice_number': {'value': '', 'accuracy': 0}, 'qr_invoice_value': {'value': '', 'accuracy': 0},
             'qr_invoice_date': {'value': '', 'accuracy': 0}, 'qr_total_item': {'value': '', 'accuracy': 0},
             'qr_hsn_code': {'value': '', 'accuracy': 0}, 'qr_hash_code': {'value': '', 'accuracy': 0}}],
               'table_data': [[[{'key': 0, 'item_quantity': {'value': 1.0, 'accuracy': 99.97},
                                 'item_unit_price': {'value': 541.1, 'accuracy': 99.98},
                                 'item_description': {'value': 'Redeem Reference Number: PO02529', 'accuracy': 99.99},
                                 'item_total_amount': {'value': 54110.0, 'accuracy': 99.95}}]]]}
        _logger.info("Response : {}".format(res))
        self.remove_file_from_local_system(file_path)
        log_id = self.create_log_for_upload(res, file_path.split('/')[-1:][0])
        return self.prepare_invoice_data(res, log_id)

    def prepare_invoice_data(self, data, log_id):
        invoice_vals = {}
        contain_tax = False
        tax_missing = False
        for rec in data.get('data', []):
            partner_id = self.find_partner(rec)
            payment_term_name = rec.get('payment_terms', {}).get('value', '')
            payment_term_id = self.env["account.payment.term"].search(
                [('name', '=ilike', '{} Days'.format(payment_term_name))], limit=1)
            invoice_vals = self.prepare_vals_for_invoice(rec, partner_id, payment_term_id)
            contain_tax = self.is_response_contain_tax_amount(rec)
        item_list = []
        taxes_not_found = ''
        for line in data.get('table_data', []):
            for rec in line:
                for item in rec:
                    tax_ids, taxes_not_found = self.find_tax_ids_from_data(item, taxes_not_found)
                    if contain_tax and not item.get('item_rate', {}).get('value', ''):
                        tax_missing = True
                    product_name = item.get('item_description', {}).get('value', '')
                    if product_name:
                        vals = {
                            'name': product_name,
                            'price_unit': item.get('item_unit_price', {}).get('value', 0),
                            'quantity': item.get('item_quantity', {}).get('value', 0),
                            'tax_ids': [(6, 0, tax_ids._ids)],
                        }
                        product_id = self.find_product_based_on_name(product_name)
                        if product_id:
                            vals.update({
                                'product_id': product_id.id,
                                'product_uom_id': product_id.uom_id.id,
                            })
                        item_list.append((0, 0, vals))
        invoice_vals.update({'invoice_line_ids': item_list})
        try:
            invoice = self.env["account.move"].create(invoice_vals)
        except Exception as e:
            raise UserError(e)
        log_id.write({'invoice_id': invoice.id})
        invoice.message_post(body=data)
        if taxes_not_found:
            invoice.message_post(body="Given Taxes is not available in Odoo {}".format(taxes_not_found))
        if tax_missing:
            invoice.message_post(body="No tax rate found from the response")
        if not item_list:
            invoice.message_post(body="Response does not contain invoice line please add line manually")
        self.check_accuracy_and_post_message(invoice, data)
        return invoice

    def find_taxes_from_data(self, rec):
        total_cgst = rec.get('total_cgst').get('value', 0)
        total_sgst = rec.get('total_sgst', {}).get('value', 0)
        total_amount = rec.get('invoice_amount', {}).get('value')
        untax_amount = total_amount - total_cgst - total_sgst
        tax_id = self.env["account.tax"]
        if total_sgst or total_cgst:
            tax_percent = round(((total_sgst + total_cgst) / untax_amount) * 100)
            if tax_percent:
                if total_cgst and total_sgst:
                    tax_id = self.get_tax_based_on_percent(tax_percent)
        return tax_id

    def find_tax_ids_from_data(self, item, taxes_not_found):
        tax_ids = self.env["account.tax"]
        item_rate = item.get('item_rate', {}).get('value', '')
        if item_rate:
            tax_ids = self.get_tax_based_on_percent(int(item_rate))
            if not tax_ids:
                taxes_not_found += "<br/>{}".format(str(item_rate))
        return tax_ids, taxes_not_found

    def get_tax_based_on_percent(self, percent, igst=False):
        domain = [('type_tax_use', '=', 'purchase'), ('name', '=ilike', 'GST {}%'.format(percent))]
        if igst:
            domain.pop()
            domain.append(('name', '=ilike', 'IGST {}%'.format(percent)))
        return self.env["account.tax"].search(domain, limit=1)

    def get_converted_date(self, date):
        try:
            date = datetime.strptime(date, '%d-%m-%Y')
        except Exception as e:
            try:
                date = datetime.strptime(date, '%d-%m-%y')
            except Exception as e:
                try:
                    date = datetime.strptime(date, '%d/%m/%Y')
                except Exception as e:
                    try:
                        date = datetime.strptime(date, '%d/%m/%y')
                    except Exception as e:
                        try:
                            date = datetime.strptime(date, '%m/%d/%Y')
                        except Exception as e:
                            try:
                                date = datetime.strptime(date, '%m/%d/%y')
                            except Exception as e:
                                try:
                                    date = datetime.strptime(date, '%d.%m.%Y')
                                except Exception as e:
                                    try:
                                        date = datetime.strptime(date, '%d.%m.%y')
                                    except Exception as e:
                                        try:
                                            date = datetime.strptime(date, '%d-%b-%y')
                                        except Exception as e:
                                            try:
                                                date = datetime.strptime(date, '%d-%b-%Y')
                                            except Exception as e:
                                                try:
                                                    date = datetime.strptime(date, '%d.%m.%y')
                                                except Exception as e:
                                                    raise UserError("Date {} format is not valid".format(date))
        return date

    def find_partner(self, rec):
        name = rec.get('supplier_name', {}).get('value', '')
        gst = rec.get('supplier_gstin', {}).get('value', '')
        pan_no = rec.get('pan_number', {}).get('value', '')
        email = rec.get('supplier_email', {}).get('value', '')
        partner_id = self.env["res.partner"]
        if gst or pan_no:
            partner_id = partner_id.search(
                ['|', ('vat', '=ilike', gst), ('vat', '=ilike', pan_no), ('supplier_rank', '>', 0)], limit=1)
        if not partner_id and name:
            partner_id = self.env["res.partner"].search(
                [('name', '=ilike', name), ('supplier_rank', '>', 0), ('email', '=ilike', email)], limit=1)
        if not partner_id:
            raise UserError("No any vendor found with Name '{}' or GST '{}'".format(name, gst))
        return partner_id

    def find_tax_based_on_total(self, rec):
        total_cgst = rec.get('total_cgst', {}).get('value')
        total_sgst = rec.get('total_sgst', {}).get('value')
        total_cgst_rate = rec.get('total_cgst_rate', {})
        total_sgst_rate = rec.get('total_sgst_rate', {})
        if total_cgst or total_sgst:
            tax_id = self.find_taxes_from_data(rec)
        if total_cgst_rate or total_sgst_rate:
            tax_id = self.get_tax_based_on_percent(
                rec.get('total_cgst_rate', {}).get('value') or rec.get('total_sgst_rate', '').get('value'))
        return tax_id

    def prepare_vals_for_invoice(self, rec, partner_id, payment_term_id):
        invoice_date = rec.get('invoice_date', {}).get('value', '')
        invoice_date = self.get_converted_date(invoice_date)
        return {
            'ref': rec.get('invoice_number').get('value', ''),
            'move_type': 'in_invoice',
            'invoice_date': invoice_date and invoice_date.date() or '',
            'invoice_origin': rec.get('po_number').get('value', ''),
            'invoice_user_id': self.env.user.id,
            'narration': rec.get('irn', {}).get('value'),
            'partner_id': partner_id.id,
            'fiscal_position_id': self.env['account.fiscal.position'].get_fiscal_position(partner_id.id),
            'partner_shipping_id': partner_id.id,
            'currency_id': partner_id.currency_id.id,
            'amount_tax': rec.get('total_tax_amount', {}).get('value', 0),
            'amount_total': rec.get('invoice_amount', {}).get('value'),
            'invoice_payment_term_id': payment_term_id.id,
        }

    def find_product_based_on_name(self, name):
        return self.env["product.product"].search([('name', '=ilike', name)], limit=1)

    def is_response_contain_tax_amount(self, rec):
        contain_tax = False
        if rec.get('total_cgst', {}).get('value', 0):
            contain_tax = True
        if rec.get('total_sgst', {}).get('value', 0):
            contain_tax = True
        if rec.get('total_igst', {}).get('value', 0):
            contain_tax = True
        return contain_tax

    def get_data_from_attachment(self, attachment):
        if len(attachment) > 1:
            raise UserError("Multiple attachment found")
        attachment = self.env["ir.attachment"].browse(attachment)
        datafile = open('/tmp/{}'.format(attachment.name), 'wb')
        try:
            datafile.write((base64.b64decode(attachment.datas)))
        except Exception as e:
            raise UserError("Error {} comes at the time of storing file".format(e))
        datafile.close()
        invoice = self.env["master.india.instance"].get_file_data('/tmp/{}'.format(attachment.name))
        if invoice:
            attachment.sudo().write({'res_id': invoice.id, 'res_model': invoice._name})
        return self.open_created_bill(invoice)

    def open_created_bill(self, invoice):
        return {
            'name': _('Generated Documents'),
            'domain': [('id', '=', invoice.id)],
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'context': self._context,
            'views': [[False, "form"]],
            'view_mode': 'form',
            'res_id': invoice.id,
        }

    def check_accuracy_and_post_message(self,invoice,data):
        data = data.get('data',{})
        instance = self.get_instance()
        invalid_accuracy = ''
        for invoice_data in data:
            for key in invoice_data.keys():
                accuracy = invoice_data.get(key,{}).get('accuracy')
                if key in ACCURACY_FIELD and invoice_data.get(key,{}).get('value') and accuracy < instance.accuracy:
                    index = ACCURACY_FIELD.index(key)
                    invalid_accuracy += '<br/> {} : {} '.format(FIELD_VALUE[index], accuracy)
        if invalid_accuracy:
            message = "Given field contain low accuracy please check it once {}".format(invalid_accuracy)
            invoice.message_post(body=message)