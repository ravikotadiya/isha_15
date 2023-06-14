from odoo import fields, models, api


class MasterIndiaLog(models.Model):
    _name = 'master.india.log'
    _description = 'Master India Log'
    _order = 'id desc'

    name = fields.Char(string="Name")
    response = fields.Text(string="Response")
    invoice_id = fields.Many2one("account.move", string="Invoice")

