def get_erp_item_master():
    data = frappe.db.sql("""
        select
            item_code as sku,
            description,
            quality,
            stock_uom,
            purchase_uom,
            custom_is_manufactured as is_manufactured,
            is_purchase_item,
            is_sales_item,
            is_sub_contracted_item,
            include_item_in_manufacturing
        from
            `tabItem`;
        """, as_dict=1)
    return data

frappe.response["message"] = get_erp_item_master()
