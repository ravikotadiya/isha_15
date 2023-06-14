import logging
import requests
import json
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import os

_logger = logging.getLogger(__name__)


class MasterIndiaInstance(models.Model):
    _name = "master.india.instance"

    name = fields.Char(string="Name", required="1")
    user_name = fields.Char(string="User Name")
    password = fields.Char(string="Password")
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)
    token = fields.Char(string="Token")
    token_update_time = fields.Datetime(string="Token Update Time")
    accuracy = fields.Float(string="Accuracy", default=50, tracking=True)

    def get_instance(self):
        return self.search([('company_id', '=', self.env.company.id)], limit=1)

    def get_auth_toekn(self, create_token=False):
        instance = self.get_instance()
        if not instance:
            raise UserError("No any instance found for company {}".format(self.env.company.name))
        token = instance.token
        if not token or create_token or (
                token and instance.token_update_time <= (datetime.now() - timedelta(hours=22))) or create_token:
            params = {
                'username': instance.user_name,
                'password': instance.password,
            }
            _logger.info("Token request initiate")
            response = requests.post('https://api-platform.mastersindia.co/api/v1/token-auth/', data=params)
            result = json.loads(response.text)
            if response.status_code == 200:
                token = result.get('token')
                if token:
                    instance.write({'token': token, 'token_update_time': datetime.now()})
                return token
            error = result.get('error') or result
            raise UserError(error)
        return token

    def get_file_data(self, file_path, create_token=False):
        response = self.make_request_and_get_response(file_path, create_token)
        result = json.loads(response.text)
        if response.status_code == 200:
            return result
        else:
            if response.status_code == 401 and 'Signature has expired' in result.get('error', '') and not create_token:
                response = self.make_request_and_get_response(file_path, create_token=True)
                result = json.loads(response.text)
                if response.status_code == 200:
                    return result
                else:
                    error = result.get('error') or result
                    raise UserError(error)
                error = result.get('error') or result.get('message', '')
            raise UserError(error)

    def make_request_and_get_response(self, file_path, create_token):
        auth_token = self.get_auth_toekn(create_token)
        if not auth_token:
            raise UserError("No Auth token found")
        headers = {
            'Authorization': 'JWT {}'.format(auth_token),
            'Subid': '435',
            'Productid': 'arap',
        }

        files = {
            'file_url': open(file_path, 'rb'),
        }
        _logger.info("upload request initiate")
        response = requests.post('https://api-platform.mastersindia.co/api/v1/ocr/upload/', headers=headers,
                                 files=files)
        _logger.info("Response come for uploaded data")
        return response

    def remove_file_from_local_system(self, file_to_remove):
        try:
            os.remove(file_to_remove)
        except Exception as e:
            _logger.info(
                "Error {} comes at the time of remove file {} from the path {}".format(e, path, file_to_remove))

    def create_log_for_upload(self, result, file_path, invoice=False):
        return self.env["master.india.log"].create({
            'name': file_path,
            'response': result,
            'invoice_id': invoice.id if invoice else False
        })
