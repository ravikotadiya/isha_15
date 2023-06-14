import json
import io
import binascii
import tempfile
from datetime import datetime
import xlrd
from tempfile import TemporaryFile
from odoo import _
from odoo.exceptions import UserError, ValidationError
from odoo import http
from odoo.http import request
from datetime import date
from odoo.addons.sale.controllers import portal
from werkzeug.wrappers import Response
import logging

_logger = logging.getLogger(__name__)

try:
    import xlrd
except ImportError:
    _logger.debug('Cannot `import xlrd`.')
try:
    import csv
except ImportError:
    _logger.debug('Cannot `import csv`.')
try:
    import base64
except ImportError:
    _logger.debug('Cannot `import base64`.')


class CustomerPortal(portal.CustomerPortal):
    @http.route('/create_update_quote', type='http', auth="user",
                website=True)
    def create_update_quote(self, **kwargs):
        sale_order = request.env['sale.order'].sudo()  # sale order object

        file = kwargs.get('attachment')
        if file:
            keys = ['product', 'quantity', 'uom', 'description']
            not_found = {'product': [], 'uom': [], 'tax': [], 'route': [], 'lot': []}
            duplicate_found = {'product': [], 'uom': [], 'tax': [], 'route': [], 'lot': []}
            empty_row = {'product': [], 'uom': [], 'price_unit': [], 'quantity': []}
            order = []
            line_data = {}
            order_line = []
            if kwargs.get('file_type', 'xlsx') == 'csv':
                try:
                    csv_data = file.read()
                    # csv_data = base64.b64decode(file_content)
                    data_file = io.StringIO(csv_data.decode("utf-8"))
                    data_file.seek(0)
                    file_reader = []
                    csv_reader = csv.reader(data_file, delimiter=',')
                    file_reader.extend(csv_reader)
                except Exception:
                    print(Exception)
                    raise ValidationError(_("Please select any file or You have selected invalid file"))

                for i in range(len(file_reader)):
                    field = list(map(str, file_reader[i]))
                    values = dict(zip(keys, field)) or {}
                    if values:
                        if i == 0:
                            continue
                        else:
                            values, empty_row = self.get_values(values, i, field, empty_row,
                                                                kwargs.get('file_type', 'csv'))
                            order_line.append(values)
                            is_error, not_found, duplicate_found = self.validate_data(values, not_found,
                                                                                      duplicate_found,
                                                                                      kwargs.get('file_type', 'csv'))
            else:
                try:
                    fp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
                    csv_data = file.read()
                    fp.write(csv_data)
                    fp.seek(0)
                    values = {}
                    workbook = xlrd.open_workbook(fp.name)
                    sheet = workbook.sheet_by_index(0)
                except Exception:
                    raise ValidationError(_("Please select any file or You have selected invalid file"))

                for row_no in range(sheet.nrows):
                    values = {}
                    val = {}
                    if row_no <= 0:
                        fields = map(lambda row: row.value.encode('utf-8'), sheet.row(row_no))
                    else:
                        line = list(
                            map(lambda row: isinstance(row.value, bytes) and row.value.encode('utf-8') or str(
                                row.value),
                                sheet.row(row_no)))
                        values, empty_row = self.get_values(values, row_no + 1, line, empty_row,
                                                            kwargs.get('file_type', 'xlsx'))
                        order_line.append(values)
                        is_error, not_found, duplicate_found = self.validate_data(values, not_found,
                                                                                  duplicate_found,
                                                                                  kwargs.get('file_type', 'xlsx'))
            validation_error = self.prepare_validation_message(empty_row, not_found, duplicate_found)
            # consolidated validations

        if not validation_error:
            # if found sale_order_reference then need to update sale order line else create new one.
            if kwargs.get('sale_order_reference'):
                sale_order = sale_order.browse(int(kwargs.get('sale_order_reference')))
                request.env['sale.order.line'].sudo().search(
                    [(
                        'order_id', '=',
                        sale_order.id)]).unlink()  # if need to update then remove all line and create new
            else:
                sale_order = sale_order.create({
                    'partner_id': request.env.user.partner_id.id,
                    'fiscal_position_id': request.env.user.partner_id.property_account_position_id.id
                })
                sale_order.sudo().onchange_partner_id()  # On change for set fiscal_position_id,pricelist and priceing policy
            self.create_order_lines(sale_order, order_line)
            sale_order.sudo().write({
                'state': 'sent',
            })
            # create attachment and link with SO
            attachment = request.env['ir.attachment'].sudo().create({
                'name': "{}_{}_{}".format(sale_order.name, date.today(), file.filename or ''),
                'res_model': 'sale.order',
                'res_id': sale_order.id,
                'type': 'binary',
                'datas': base64.b64encode(csv_data),
                'mimetype': "application / vnd.openxmlformats - officedocument.spreadsheetml.sheet",
            })
            # Message post with attachment
            sale_order.sudo().message_post(body=_('Generate Order via {}'.format(attachment.name)),
                                           attachments=[(attachment.name, attachment.datas)], )
        if validation_error:
            json_data = json.dumps({'result': 'error', 'log': validation_error})
        else:
            json_data = json.dumps({'result': 'sucess'})

        return Response(json_data, content_type='application/json')

    # Sub-method which read xlxs file and return values
    def get_values(self, values, row_no, excel_value, empty_row, type):
        if type == 'xlsx':
            values.update({'product': excel_value[0],
                           'quantity': excel_value[1],
                           'uom': excel_value[2],
                           'description': excel_value[3],
                           'price_unit': excel_value[4],
                           'row_no': row_no,
                           })
        else:
            values.update({
                'product': excel_value[0],
                'quantity': excel_value[1],
            })
        if not values.get('product'):
            empty_row.get('product').append(str(values.get('row_no')))
        if not values.get('uom'):
            empty_row.get('uom').append(str(values.get('row_no')))
        if not values.get('quantity'):
            empty_row.get('quantity').append(str(values.get('row_no')))
        price_unit = values.get('price_unit', False)
        if not price_unit:
            empty_row.get('price_unit').append(str(values.get('row_no')))
        else:
            try:
                temp_price_unit = float(price_unit)
                if temp_price_unit <= 0:
                    empty_row.get('price_unit').append(str(values.get('row_no')))
            except ValueError:
                empty_row.get('price_unit').append(str(values.get('row_no')))

        return values, empty_row

    def validate_data(self, values, not_found, duplicate_found, type):
        product = values.get('product')
        is_error = False
        # for Product
        if type == 'xlsx':
            if not product:
                not_found.get('product').append(str(values.get('row_no')) + ':' + product)
                is_error = True
            if product:
                product_id = self.search_product(product)
                if product_id:
                    if len(product_id) > 1:
                        duplicate_found.get('product').append(product)
                        is_error = True
                else:
                    not_found.get('product').append(str(values.get('row_no')) + ':' + product)
                    is_error = True
            # UOM
            uom = values.get('uom')
            if uom:
                uom_id = self.search_uom(uom)
                if not uom_id:
                    not_found.get('uom').append(str(values.get('row_no')) + ':' + uom)
                    is_error = True
                else:
                    if len(uom_id) > 1:
                        duplicate_found.get('uom').append(str(values.get('row_no')) + ':' + uom)
                        is_error = True
            else:
                not_found.get('uom').append(str(values.get('row_no')) + ':' + product)
                is_error = True

        return is_error, not_found, duplicate_found

    def search_product(self, product, limit=80):
        return request.env['product.product'].sudo().search([('default_code', '=ilike', product)], limit=limit)

    def search_uom(self, uom, limit=80):
        return request.env['uom.uom'].sudo().search([('name', '=ilike', uom)], limit=limit)

    def prepare_validation_message(self, empty_row, not_found, duplicate_found):
        validation_error = ''
        empty_row_product = empty_row.get('product')
        if empty_row_product:
            validation_error += "Below Rows the SKU is missing:\n" + str(empty_row_product) + '\n\n'

        empty_row_uom = empty_row.get('uom')
        if empty_row_uom:
            validation_error += "Below Rows the UOM is missing:\n" + str(empty_row_uom) + '\n\n'

        empty_row_price_unit = empty_row.get('price_unit')
        if empty_row_price_unit:
            validation_error += "Below Rows the Cost is missing:\n" + str(empty_row_price_unit) + '\n\n'
        empty_row_quantity = empty_row.get('quantity')
        if empty_row_quantity:
            validation_error += "Below Rows the Quantity is missing:\n" + str(empty_row_quantity) + '\n\n'

        lot_not_found = not_found.get(
            'lot')  # for lot we can set the empty row becase it's based on the product tracking so added in not_found otherwise it will be in the empty row
        if lot_not_found:
            validation_error += "Below Rows the Lot OR Expiration date is missing\n" + str(
                lot_not_found) + '\n\n'

        product_not_found = not_found.get('product')
        if product_not_found:
            validation_error += "Below SKU are not found\n" + str(product_not_found) + '\n\n'

        duplicate_product_found = duplicate_found.get('product')
        if duplicate_product_found:
            validation_error += "Duplicate Product found for Below SKU \n" + str(duplicate_product_found) + '\n\n'

        uom_not_found = not_found.get('uom')
        if uom_not_found:
            validation_error += "Below UOM are not found\n" + str(uom_not_found) + '\n\n'

        duplicate_uom = duplicate_found.get('uom')
        if duplicate_uom:
            validation_error += "Duplicate UOM found for \n" + str(duplicate_uom) + '\n\n'
        return validation_error

    # Method which validate xlsx file and create order line
    def create_order_lines(self, order, values):
        for rec in values:
            product_id = self.search_product(rec.get('product'))
            uom_id = self.search_uom(rec.get('uom'))
            line = request.env['sale.order.line'].sudo().create({
                'product_id': product_id.id,
                'name': rec.get('description', ''),
                'product_uom_qty': rec.get('quantity') or product_id.display_name,
                'order_id': order.id,
                'product_uom': uom_id.id,
                'price_unit': float(rec.get('price_unit', 0))
            })
            print(line)
        ##line.product_id_change()
        # line.product_uom_change()
