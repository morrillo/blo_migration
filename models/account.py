#!/usr/bin/python
# -*- coding: utf-8 -*-

# Imports python libraries

import sys
import xmlrpc.client
import ssl

import psycopg2

# load the psycopg extras module
import psycopg2.extras

from odoo import fields, models, api
from odoo.exceptions import ValidationError
from datetime import datetime

# creates original_id fields on models


class AccountMove(models.Model):
    _inherit = 'account.move'

    original_id = fields.Integer('Original ID')


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    original_id = fields.Integer('Original ID')


class AccountAccount(models.Model):
    _inherit = 'account.account'

    original_id = fields.Integer('Original ID')


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    original_id = fields.Integer('Original ID')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    original_id = fields.Integer('Original ID')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    original_id = fields.Integer('Original ID')


class ProductTemplae(models.Model):
    _inherit = 'product.template'

    original_id = fields.Integer('Original ID')

# In res.company model (for no particular reason) I create two methods for migrating invoices


class ResCompany(models.Model):
    _inherit = 'res.company'

    # receives as parameter a dictionary which contains the following fields:
    # product_id, qty, discount, price_unit, original_id
    # returns a dictionary with the invoice_line formatted for being created
    # with the invoice
    def _prepare_invoice_line(self, invoice_line):
        # Validates that product is present in master data
        # by check the original_id field
        # original_id holds the id from previous Odoo database
        # Cancels method execution in case of product not being present
        # in the database
        product = self.env['product.product'].search(
            [('original_id', '=', invoice_line['product_id'])])
        if not product:
            raise ValidationError('There is no product defined for original ID %s' % (
                invoice_line['product_id']))
        # Formats the invoice_line dictionary as a different dictionary
        # Adds product taxes to the return dictionary
        return {
            'product_id': product.id,
            'quantity': invoice_line['qty'],
            'discount': invoice_line['discount'],
            'price_unit': invoice_line['price_unit'],
            'name': invoice_line['name'],
            'tax_ids': [(6, 0, product.taxes_id.ids)],
            'product_uom_id': product.uom_id.id,
            'original_id': invoice_line['original_id'],
        }

    # Migrates invoices from Odoo instance
    # The connection is done with xmlrpc

    @api.model
    def migrate_invoices(self):
        # Pulls connection parameters from system parameters
        # If any of the parameters is not present, a message error
        # is displayed
        dbname = self.env['ir.config_parameter'].get_param('DBNAME', None)
        host = self.env['ir.config_parameter'].get_param('HOST', None)
        username = self.env['ir.config_parameter'].get_param('USER', None)
        pwd = self.env['ir.config_parameter'].get_param('PWD', None)
        if not dbname or not host or not username or not pwd:
            raise ValidationError(
                'One of the connection parameters is missing')

        url, db, username, password = host, dbname, username, pwd

        # Makes the connection to the remote database
        # in case there is a problem (which is checked with the uid variable)
        # an error message is displayed

        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
        common.version()
        uid = common.authenticate(db, username, pwd, {})

        models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
        if not uid or not models:
            raise ValidationError(
                'Connection error.\nPlease check with your administrator')

        # Pulls the IDs from the remote posted invoices
        invoice_ids = models.execute_kw(db, uid, pwd, 'account.invoice', 'search', [
                                        [('state', 'in', ['open', 'paid'])]])
        # Iterates the IDs of remote invoices
        for invoice_id in invoice_ids:
            # Reads remote invoice data
            invoice_data = models.execute_kw(
                db, uid, pwd, 'account.invoice', 'read', [invoice_id])
            invoice_data = invoice_data[0]
            # Checks remote journal is present in target database
            journal_id = self.env['account.journal'].search(
                [('original_id', '=', invoice_data['journal_id'][0])])
            if not journal_id:
                raise ValidationError('There is no journal for original_ID %s' % (
                    invoice_data['journal_id'][0]))
            # Checks remote invoice partner is present in target database
            partner_id = self.env['res.partner'].search(
                [('original_id', '=', invoice_data['partner_id'][0])])
            if not partner_id:
                raise ValidationError('There is no partner_id for original_ID %s' % (
                    invoice_data['partner_id'][0]))
            invoice_lines = []
            # Iterates remote invoice lines. Adds remote invoice line data
            # to invoice_lines list
            for invoice_line_id in invoice_data['invoice_line_ids']:
                # Reads remote invoice_line information
                line_data = models.execute_kw(
                    db, uid, pwd, 'account.invoice.line', 'read', [invoice_line_id])
                line_data = line_data[0]
                vals_line = {
                    'product_id': line_data['product_id'][0],
                    'qty': line_data['quantity'],
                    'discount': line_data['discount'],
                    'price_unit': line_data['price_unit'],
                    'name': line_data['name'],
                    'original_id': invoice_line_id,
                }
                invoice_lines.append(vals_line)
            # Creates dictionary with account.move values
            # iterates invoice_lines list in order to update invoice_line_ids field
            vals_move = {
                'move_type': invoice_data['type'],
                'invoice_date': invoice_data['date_invoice'],
                'journal_id': journal_id.id,
                'invoice_origin': invoice_data['origin'],
                'original_id': invoice_id,
                'narration': invoice_data['comment'],
                'partner_id': partner_id.id,
                'currency_id': self.env.user.company_id.currency_id.id,
                'invoice_line_ids': [(0, None, self._prepare_invoice_line(line)) for line in invoice_lines],
            }
            # 'invoice_line_ids': [(0, None, self._prepare_invoice_line(line)) for line in self.lines],
            # Checks the invoice has not been created before
            move_id = self.env['account.move'].search(
                [('original_id', '=', invoice_id)])
            if not move_id:
                # In case it was not created, creates the move. Move is in draft state
                # it is not posted yet
                move_id = self.env['account.move'].create(vals_move)

    @api.model
    def migrate_sql_invoices(self):
        #raise ValidationError('estamos aca')
        dbname = self.env['ir.config_parameter'].get_param('SQL_DBNAME', None)
        host = self.env['ir.config_parameter'].get_param('SQL_HOST', None)
        username = self.env['ir.config_parameter'].get_param('SQL_USER', None)
        pwd = self.env['ir.config_parameter'].get_param('SQL_PWD', None)
        if not dbname or not host or not username or not pwd:
            raise ValidationError(
                'One of the connection parameters is missing')
        connect_string = "dbname='%s' user='%s' host='%s' password='%s'" % (
            dbname, username, host, pwd)
        try:
            conn = psycopg2.connect("dbname='%s' user='%s' host='%s' password='%s'" % (
                dbname, username, host, pwd))
        except:
            raise ValidationError("I am unable to connect to the database")

        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                "select * from account_invoice where type = 'out_invoice' and state in ('open','paid')")
        except:
            raise ValidationError('Problems querying the invoice table')
        rows = cur.fetchall()
        for invoice_data in rows:
            journal_id = self.env['account.journal'].search(
                [('original_id', '=', invoice_data['journal_id'])])
            partner_id = self.env['res.partner'].search(
                [('original_id', '=', invoice_data['partner_id'])])
            if not partner_id:
                raise ValidationError(
                    'There is no partner_id for original_ID %s' % (invoice_data['partner_id']))
            if not journal_id:
                raise ValidationError(
                    'There is no journal for original_ID %s' % (invoice_data['journal_id']))
            invoice_id = invoice_data['id']
            cur_lines = conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                cur_lines.execute(
                    "select * from account_invoice_line where invoice_id = %s" % (invoice_id))
            except:
                raise ValidationError('Problems querying the invoice table')
            invoice_lines = []
            row_lines = cur_lines.fetchall()
            for invoice_line in row_lines:
                vals_line = {
                    'product_id': invoice_line['product_id'],
                    'qty': invoice_line['quantity'],
                    'discount': invoice_line['discount'],
                    'price_unit': invoice_line['price_unit'],
                    'name': invoice_line['name'],
                    'original_id': invoice_line['id'],
                }
                invoice_lines.append(vals_line)
            vals_move = {
                'type': invoice_data['type'],
                'invoice_date': invoice_data['date_invoice'],
                'journal_id': journal_id.id,
                'invoice_origin': invoice_data['origin'],
                'original_id': invoice_id,
                'narration': invoice_data['comment'],
                'partner_id': partner_id.id,
                'currency_id': self.env.user.company_id.currency_id.id,
                'invoice_line_ids': [(0, None, self._prepare_invoice_line(line)) for line in invoice_lines],
            }
            move_id = self.env['account.move'].search(
                [('original_id', '=', invoice_id)])
            if not move_id:
                move_id = self.env['account.move'].create(vals_move)
            cur_lines.close()
        cur.close()
