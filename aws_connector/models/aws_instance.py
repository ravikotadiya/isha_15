import logging
import requests
import json
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import os

_logger = logging.getLogger(__name__)


class AwsInstance(models.Model):
    _name = "aws.instance"
    _description = "AWS Instance"

    name = fields.Char(string="Name", required="1")
    access_key = fields.Char(string="Access Key")
    secret_key = fields.Char(string="Secret Key")
    region = fields.Char(string="Region")
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)


