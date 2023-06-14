# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import Warning, ValidationError
import binascii
import tempfile
from datetime import datetime
import xlrd
from tempfile import TemporaryFile
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)
import io

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


class StockMoveWizard(models.TransientModel):
    _name = 'stock.move.wizard'
    _description = "Stock Move Wizard"

    import_file = fields.Binary(string="Select File")
    import_option = fields.Selection([('csv', 'CSV File'), ('xls', 'XLS File')], string='Select', default='xls')
    import_prod_option = fields.Selection([('barcode', 'Barcode'), ('code', 'Code'), ('name', 'Name')],
                                          string='Import Product By ', default='code')
    product_details_option = fields.Selection(
        [('from_product', 'Take Details From The Product'), ('from_xls', 'Take Details From The XLS File'),
         ('from_pricelist', 'Take Details With Adapted Pricelist')], default='from_xls')

    sample_option = fields.Selection([('csv', 'CSV'), ('xls', 'XLS')], string='Sample Type', default='xls')
    down_samp_file = fields.Boolean(string='Download Sample Files')
    company_id = fields.Many2one(
        'res.company', 'Company', copy=False,
        required=True, index=True, default=lambda s: s.env.company)

    def get_values(self, values, row_no, excel_value, empty_row):
        if self.product_details_option == 'from_product':
            values.update({
                'product': excel_value[0],
                'quantity': excel_value[1]
            })
        elif self.product_details_option == 'from_xls':
            values.update({'product': excel_value[0],
                           'quantity': excel_value[1],
                           'uom': excel_value[2],
                           'description': excel_value[3],
                           'lot': excel_value[4],
                           'expiration_date': excel_value[5],
                           'price_unit': excel_value[6],
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
        price_unit = values.get('price_unit',False)
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

    def import_stock_move(self):
        res = False
        not_found = {'product': [], 'uom': [], 'tax': [], 'route': [], 'lot': []}
        duplicate_found = {'product': [], 'uom': [], 'tax': [], 'route': [], 'lot': []}
        empty_row = {'product': [], 'uom': [], 'price_unit': [], 'quantity': []}
        stock_move = []
        stock_move_line = {}
        stock_picking_obj = self.env['stock.picking'].sudo()
        stock_move_obj = self.env['stock.move'].sudo()
        stock_picking_record = stock_picking_obj.browse(self._context.get('active_id'))
        if stock_picking_record.state not in ('draft'):
            raise UserError(_('Sorry!!!, We can import the data only in draft stage.'))
        stock_picking_record.move_lines = False
        stock_picking_record.move_line_ids = False
        if self.import_option == 'csv':
            keys = ['product', 'quantity', 'uom', 'description', 'lot']
            try:
                csv_data = base64.b64decode(self.import_file)
                data_file = io.StringIO(csv_data.decode("utf-8"))
                data_file.seek(0)
                file_reader = []
                csv_reader = csv.reader(data_file, delimiter=',')
                file_reader.extend(csv_reader)

            except Exception:
                raise ValidationError(_("Please select any file or You have selected invalid file"))

            values = {}
            for i in range(len(file_reader)):
                field = list(map(str, file_reader[i]))
                values = dict(zip(keys, field))
                if values:
                    if i == 0:
                        continue
                    else:
                        values, empty_row = self.get_values(values, i, field, empty_row)
                        not_found, duplicate_found, stock_move, stock_move_line = self.create_stock_move(values,
                                                                                                         not_found,
                                                                                                         duplicate_found,
                                                                                                         stock_move,
                                                                                                         stock_move_line)
        else:
            try:
                fp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
                fp.write(binascii.a2b_base64(self.import_file))
                fp.seek(0)
                values = {}
                workbook = xlrd.open_workbook(fp.name)
                sheet = workbook.sheet_by_index(0)
            except Exception:
                raise ValidationError(_("Please select any file or You have selected invalid file"))

            for row_no in range(sheet.nrows):
                val = {}
                if row_no <= 0:
                    fields = map(lambda row: row.value.encode('utf-8'), sheet.row(row_no))
                else:
                    line = list(
                        map(lambda row: isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value),
                            sheet.row(row_no)))

                    values, empty_row = self.get_values(values, row_no, line, empty_row)

                    not_found, duplicate_found, stock_move, stock_move_line = self.create_stock_move(values, not_found,
                                                                                                     duplicate_found,
                                                                                                     stock_move,
                                                                                                     stock_move_line)

        # consolidated validations
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
            validation_error += "Below Rows the Lot OR Expiration date is missing\n" + str(lot_not_found) + '\n\n'

        product_not_found = not_found.get('product')
        if product_not_found:
            validation_error += "Below SKU are not found\n" + str(product_not_found) + '\n\n'

        uom_not_found = not_found.get('uom')
        if uom_not_found:
            validation_error += "Below UOM are not found\n" + str(uom_not_found) + '\n\n'

        if validation_error:
            raise ValidationError(
                _('Kindly fix below errors to proceed: .\n %s ') % validation_error)
        if stock_move:
            # Sum the Qty based on the stock move product
            dict_stock_move = {}
            stock_move_mapping = {}
            final_stock_move_line = []
            for move in stock_move:
                key = (move.get('product_id'), move.get('product_uom'))
                if key not in dict_stock_move:
                    dict_stock_move.update({key: move})
                else:
                    dict_stock_move.get(key).update({
                        'product_uom_qty': float(move.get('product_uom_qty')) + float(
                            dict_stock_move.get(key).get('product_uom_qty'))
                    })

            for key, temp in dict_stock_move.items():
                temp_list = []
                temp_list.append(temp)
                res = stock_move_obj.create(temp_list)
                stock_move_mapping.update({key: {'move_id': res.id}})

            # To create the stock move lines
            for key, value in stock_move_line.items():
                stock_move_key = (value.get('product_id'), value.get('product_uom_id'))
                move_id = stock_move_mapping.get(stock_move_key).get('move_id')
                temp_val = value
                temp_val.update({'move_id': move_id})
                final_stock_move_line.append(temp_val)
            if final_stock_move_line:
                self.env['stock.move.line'].sudo().create(final_stock_move_line)
        return True

    def create_stock_move(self, values, not_found, duplicate_found, stock_move, stock_move_line):
        stock_picking_brw = self.env['stock.picking'].browse(self._context.get('active_id'))
        product = values.get('product')
        product_id = False
        is_error = False
        # for Product
        if self.product_details_option == 'from_xls':
            if not product:
                not_found.get('product').append(str(values.get('row_no')) + ':' + product)
                is_error = True
            if product:
                if self.import_prod_option == 'barcode':
                    product_obj_search = self.env['product.product'].search([('barcode', '=', product)])
                elif self.import_prod_option == 'code':
                    product_obj_search = self.env['product.product'].search([('default_code', '=', product)])
                else:
                    product_obj_search = self.env['product.product'].search([('name', '=', product)])
                if not product_obj_search:
                    product = "0"+product
                    product_obj_search = self.env['product.product'].search([('default_code', '=', product)])
                if product_obj_search:
                    if len(product_obj_search) > 1:
                        duplicate_found.get('product').append(product)
                        is_error = True
                    else:
                        product_id = product_obj_search
                        # for the lot
                        if product_id.tracking == 'lot':
                            lot_name = values.get('lot', False)
                            expiration_date = values.get('expiration_date', False)
                            if not lot_name or not expiration_date:  # for lot both are required
                                not_found.get('lot').append(str(values.get('row_no')) + ':' + product)
                                is_error = True
                else:
                    not_found.get('product').append(str(values.get('row_no')) + ':' + product)
                    is_error = True
            # UOM
            uom = values.get('uom')
            if uom:
                uom_obj_search = self.env['uom.uom'].search([('name', '=', uom)])
                if not uom_obj_search:
                    not_found.get('uom').append(str(values.get('row_no')) + ':' + uom)
                    is_error = True
                else:
                    if len(uom_obj_search) > 1:
                        duplicate_found.get('uom').append(str(values.get('row_no')) + ':' + uom)
                        is_error = True
            else:
                not_found.get('uom').append(str(values.get('row_no')) + ':' + product)
                is_error = True
            # To create Sales Order line value
            if not is_error:
                order_vals = {
                    'picking_id': stock_picking_brw.id,
                    'product_uom_qty': values.get('quantity'),
                    'location_id': stock_picking_brw.location_id.id,
                    'location_dest_id': stock_picking_brw.location_dest_id.id,
                    'product_uom': uom_obj_search[0].id,
                    'product_id': product_id[0].id,
                    'name': product_id[0].display_name,

                }
                # Price Unit .
                price_unit = values.get('price_unit')
                if price_unit:
                    order_vals.update({'price_unit': float(price_unit)})
                if values.get('description') == '' or not values.get('description'):
                    order_vals.update({'description_picking': product_id[0].display_name, })

                stock_move.append(order_vals)

                lot_id = False
                if product_id and product_id.tracking == 'lot':
                    lot_name = values.get('lot')
                    expiration_date = values.get('expiration_date')
                    lot_id = self._find_create_lot_id(lot_name, product_id, expiration_date)
                    key = (order_vals.get('product_id'), order_vals.get('product_uom'), lot_id.id)
                else:
                    key = (order_vals.get('product_id'), order_vals.get('product_uom'), lot_id)
                vals = {
                    # 'move_id': move.id,
                    'product_id': order_vals.get('product_id'),
                    # 'expiration_date': values.get('expiration_date', False),
                    'product_uom_id': order_vals.get('product_uom'),
                    'location_id': order_vals.get('location_id'),
                    'location_dest_id': order_vals.get('location_dest_id'),
                    'picking_id': stock_picking_brw.id,
                    # 'lot_name': lot_name if stock_picking_brw.picking_type_id.code == 'incoming' else False,
                    # 'lot_id': self._find_lot_id(lot_name, product_id) if stock_picking_brw.picking_type_id.code in (
                    # 'outgoing', 'internal', 'incoming') else False,
                    'qty_done': 1 if product_id.tracking == 'serial' else order_vals.get('product_uom_qty', 0),
                }
                if lot_id:
                    vals.update({'lot_id': lot_id.id, 'expiration_date': lot_id.expiration_date})

                if key not in stock_move_line:
                    stock_move_line.update({key: vals})
                else:
                    stock_move_line.get(key).update({
                        'qty_done': float(vals.get('qty_done', 0)) + float(stock_move_line.get(key).get('qty_done', 0))
                    })
                # stock_move_line.update({key: vals})

        return not_found, duplicate_found, stock_move, stock_move_line

    def _find_create_lot_id(self, lot_name, product_id, expiration_date):
        lot_obj = self.env['stock.production.lot'].sudo()
        lot = lot_obj.search([('name', '=', lot_name), ('product_id', '=', product_id.id), ('company_id', '=', self.company_id.id)], limit=1)
        temp_expiration_date = datetime.strptime(expiration_date, '%Y-%m-%d')
        if not lot:
            lot = lot_obj.create({'product_id': product_id.id,
                                  'name': lot_name,
                                  'expiration_date': temp_expiration_date,
                                  'company_id': self.env.company.id, })
        return lot or False

    def download_auto_stock_move(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=stock.move.wizard&id=%s' % (self.id),
            'target': 'new',
        }


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.constrains('name')
    def _product_name_unique(self):
        for case in self:
            if case.name and case.id:
                is_duplicated = self.env['product.template'].sudo().search_count([('name', '=', case.name), ('default_code', '=', case.default_code), ('id', '!=', case.id)])
                if is_duplicated:
                    raise UserError(
                        _("Sorry! You can not have two Products with the same name:\n %s\n") % (case.name,))
