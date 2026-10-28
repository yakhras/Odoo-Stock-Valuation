# Generated demo data for screenshots: 2 warehouses, 3 hardware products, receipts at
# different prices, deliveries, a landed cost, a revaluation and an EXO -> EXI transfer.
# Run on a throwaway DB: odoo shell -d stock_valuation_demo < tools/demo_data.py
# (scripts/module_lab.ps1 -Do up does this). 18.0 only.
env = env  # noqa: F821 (odoo shell)

admin = env.ref('base.user_admin')
admin.write({'groups_id': [(4, env.ref('stock.group_stock_multi_warehouses').id),
                           (4, env.ref('stock.group_stock_multi_locations').id),
                           (4, env.ref('account.group_account_manager').id)]})
env = env(user=admin)

company = env.company
main = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
main.write({'name': 'Main Warehouse'})
north = env['stock.warehouse'].create({'name': 'North Warehouse', 'code': 'NWH'})
supplier = env.ref('stock.stock_location_suppliers')
customer = env.ref('stock.stock_location_customers')

categ = env['product.category'].create({
    'name': 'Hardware', 'property_cost_method': 'average', 'property_valuation': 'manual_periodic'})
P = env['product.product']
bolt = P.create({'name': 'Steel Bolt M8', 'default_code': 'HW-001', 'is_storable': True, 'categ_id': categ.id})
wire = P.create({'name': 'Copper Wire 2mm', 'default_code': 'HW-002', 'is_storable': True, 'categ_id': categ.id})
panel = P.create({'name': 'LED Panel 60x60', 'default_code': 'HW-003', 'is_storable': True, 'categ_id': categ.id})
partner = env['res.partner'].create({'name': 'Demo Supplier'})


def picking(ptype, src, dest, lines, **extra):
    vals = {'picking_type_id': ptype.id, 'location_id': src.id, 'location_dest_id': dest.id,
            'partner_id': partner.id,
            'move_ids': [(0, 0, {'name': p.name, 'product_id': p.id, 'product_uom': p.uom_id.id,
                                 'product_uom_qty': q, 'price_unit': price,
                                 'location_id': src.id, 'location_dest_id': dest.id})
                         for p, q, price in lines]}
    vals.update(extra)
    pick = env['stock.picking'].create(vals)
    pick.action_confirm()
    pick.action_assign()
    for m in pick.move_ids:
        m.quantity = m.product_uom_qty
        m.picked = True
    pick.button_validate()
    return pick


# receipts at different prices per warehouse
picking(main.in_type_id, supplier, main.lot_stock_id, [(bolt, 1000, 0.40), (wire, 200, 6.00), (panel, 50, 22.00)])
picking(main.in_type_id, supplier, main.lot_stock_id, [(bolt, 500, 0.52), (wire, 100, 7.50)])
north_in = picking(north.in_type_id, supplier, north.lot_stock_id, [(bolt, 800, 0.55), (wire, 150, 8.00), (panel, 40, 25.00)])
# deliveries
picking(main.out_type_id, main.lot_stock_id, customer, [(bolt, 300, 0), (panel, 10, 0)])
picking(north.out_type_id, north.lot_stock_id, customer, [(wire, 30, 0)])

# landed cost on the North receipt
freight = P.create({'name': 'Freight', 'type': 'service', 'landed_cost_ok': True})
journal = env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)
lc = env['stock.landed.cost'].create({
    'picking_ids': [(6, 0, north_in.ids)], 'account_journal_id': journal.id,
    'cost_lines': [(0, 0, {'name': 'Freight', 'product_id': freight.id, 'price_unit': 240.0, 'split_method': 'by_quantity'})]})
lc.compute_landed_cost()
lc.button_validate()

# revaluation in Main Warehouse
env['stock.valuation.layer.revaluation'].with_context(
    default_product_id=panel.id, default_company_id=company.id,
).create({'warehouse_id': main.id, 'added_value': 80.0, 'reason': 'Supplier price correction'}
).action_validate_revaluation()

# EXO -> EXI transfer Main -> North through transit
transit = env['stock.location'].create({'name': 'Transit', 'usage': 'transit', 'company_id': company.id})
def ptype(code, name, wh, src, dest, prefix):
    return env['stock.picking.type'].create({
        'name': name, 'sequence_code': code, 'code': 'internal', 'warehouse_id': wh.id,
        'default_location_src_id': src.id, 'default_location_dest_id': dest.id})
exo_t = ptype('EXO', 'Inter-Warehouse Out', main, main.lot_stock_id, transit, 'EXO')
ptype('EXI', 'Inter-Warehouse In', north, transit, north.lot_stock_id, 'EXI')
exo = picking(exo_t, main.lot_stock_id, transit, [(bolt, 200, 0), (wire, 50, 0)],
              destination=north.lot_stock_id.id)
exi = env['stock.picking'].search([('origin', '=', exo.name)])
exi.action_confirm(); exi.action_assign()
for m in exi.move_ids:
    m.quantity = m.product_uom_qty
    m.picked = True
exi.button_validate()

# xml ids for the screenshot spec ({ref:stock_valuation_demo.<name>} in tools/screenshots.yaml)
north_bolt_cost = env['product.location.cost'].search(
    [('product_id', '=', bolt.id), ('warehouse_id', '=', north.id)], limit=1)
north_bolt_layer = env['stock.valuation.layer'].search(
    [('product_id', '=', bolt.id), ('warehouse_id', '=', north.id)], order='id', limit=1)
for name, record in (('bolt', bolt), ('panel', panel), ('company', company), ('exo', exo),
                     ('north_bolt_cost', north_bolt_cost), ('north_bolt_layer', north_bolt_layer)):
    env['ir.model.data'].create({'module': 'stock_valuation_demo', 'name': name, 'model': record._name,
                                 'res_id': record.id, 'noupdate': True})
env.cr.commit()
for c in env['product.location.cost'].search([], order='product_id, warehouse_id'):
    print('COST', c.product_id.default_code, c.warehouse_id.name, round(c.cost, 4), len(c.history_ids))
print('EXO', exo.name, exo.state, 'EXI', exi.name, exi.state)
