def get_bom():
    data = frappe.db.sql("""
        select
            bei.name as id,
            b.item as sku,
            b.name as bom_id,
            b.is_default,
            bei.item_code as raw_material_code,
            bei.description,
            bei.qty_consumed_per_unit as cons_per_unit
        from 
            `tabBOM` as b
        join 
            `tabBOM Explosion Item`as bei on b.name = bei.parent
        join
            `tabItem` as i on bei.item_code = i.item_code
        where
            b.is_default = true
            and i.custom_line is not null
            # and bei.item_code like '%FA-%'
        """, as_dict=1)
    return data

frappe.response["message"] = get_bom()
