def get_purchase_dri():
    query = """
        WITH base_data AS (

            /* =====================================================
               PART 1: NORMAL SUPPLIERS (NOT SELF)
            ===================================================== */
            SELECT
                CASE
                    WHEN poi.fg_item IS NOT NULL AND poi.fg_item != ''
                        THEN poi.fg_item
                    ELSE poi.item_code
                END AS item_code,

                po.owner AS purchase_dri_email,
                u.full_name AS purchase_dri_name,
                po.name AS po_name,
                po.transaction_date,
                po.is_subcontracted

            FROM `tabPurchase Order Item` poi
            INNER JOIN `tabPurchase Order` po
                ON po.name = poi.parent
            LEFT JOIN `tabUser` u
                ON u.name = po.owner
               AND u.enabled = 1

            WHERE
                po.docstatus = 1
                AND po.supplier_name != 'Suraaj Linens - Self'
                AND po.owner NOT IN (
                    'rajeev.yadav@suraaj.com',
                    'rupali.palshetkar@suraaj.com',
                    'kiran.rasal@suraaj.com',
                    'rajeshpjain@suraaj.com'
                )

            UNION ALL

            /* =====================================================
               PART 2: SELF SUPPLIER (FORCED DRI)
            ===================================================== */
            SELECT
                CASE
                    WHEN poi.fg_item IS NOT NULL AND poi.fg_item != ''
                        THEN poi.fg_item
                    ELSE poi.item_code
                END AS item_code,

                'r.rajeshkumar@suraaj.com' AS purchase_dri_email,
                'Rajeshkumar R' AS purchase_dri_name,
                po.name AS po_name,
                po.transaction_date,
                po.is_subcontracted

            FROM `tabPurchase Order Item` poi
            INNER JOIN `tabPurchase Order` po
                ON po.name = poi.parent

            WHERE
                po.docstatus = 1
                AND po.supplier_name = 'Suraaj Linens - Self'
        ),

        aggregated AS (
            SELECT
                item_code,
                purchase_dri_email,
                purchase_dri_name,
                COUNT(DISTINCT po_name) AS purchase_count,
                MAX(transaction_date) AS last_purchase_date,
                CASE
                    WHEN is_subcontracted = 1 THEN 'Subcontracting'
                    ELSE 'Purchase'
                END AS po_type
            FROM base_data
            GROUP BY
                item_code,
                purchase_dri_email,
                purchase_dri_name,
                is_subcontracted
        )

        SELECT
            item_code,
            purchase_dri_email,
            purchase_dri_name,
            purchase_count,
            last_purchase_date,
            po_type
        FROM (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY item_code
                    ORDER BY purchase_count DESC, last_purchase_date DESC
                ) AS rn
            FROM aggregated
        ) ranked
        WHERE rn = 1
        ORDER BY purchase_count DESC, last_purchase_date DESC
    """

    return frappe.db.sql(query, as_dict=True)


frappe.response["message"] = get_purchase_dri()
