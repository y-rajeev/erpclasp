def get_item_master():
    data = frappe.db.sql("""
        SELECT
            item.item_code AS sku,
            item.custom_line As line,
            item.custom_design AS design,
            item.custom_size AS size,
            item.custom_pcs__pack AS pcs_pack,
            item.custom_production AS production,
            REGEXP_REPLACE(item.item_name, '<[^>]*>', '') AS item_name,
            REGEXP_REPLACE(item.description, '<[^>]*>', '') AS description,
            REGEXP_REPLACE(item.item_group, '<[^>]*>', '') AS item_group,
            item.quality AS quality,
            item.custom_item_type AS item_type,
            item.custom_product_type AS product_type,
            item.stock_uom AS stock_uom,
            item.is_stock_item as is_stock_item,
            item.purchase_uom as purchase_uom,
            item.gst_hsn_code AS gst_hsn_code,
            item_tax.item_tax_template AS item_tax_template,
            item.is_purchase_item AS is_purchase_item,
            item.is_sales_item AS is_sales_item,
            item.is_sub_contracted_item AS is_sub_contracted_item,
            item.include_item_in_manufacturing AS include_item_in_manufacturing,
            item.custom_is_manufactured AS is_manufactured
        FROM
            `tabItem` AS item
        LEFT JOIN
            `tabItem Tax` AS item_tax ON item.name = item_tax.parent
        WHERE 
            item.disabled = 0
        ORDER BY
            item.creation ASC
        """, as_dict=1)
    return data

frappe.response["message"] = get_item_master()
