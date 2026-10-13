from odoo import tools

from . import models

if tools.config['test_enable']:
	from . import tests
