import base64
import os
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class UploadFileWizard(models.TransientModel):
    _name = "upload.file.wizard"

    file_data = fields.Binary("Choose File")
    file_name = fields.Char("File Name")

    def get_file_data(self):
        datafile = open('/tmp/{}'.format(self.file_name), 'wb')
        try:
            datafile.write((base64.b64decode(self.file_data)))
        except Exception as e:
            raise UserError("Error {} comes at the time of storing file".format(e))
        datafile.close()
        self.env["master.india.instance"].get_file_data('/tmp/{}'.format(self.file_name))
