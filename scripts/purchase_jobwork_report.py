def purchase_jobwork_report():
    data = frappe.db.sql("""
    WITH receipts AS (

    -- Purchase Receipts
    SELECT
        'Purchase'                                       AS receipt_type,
        pri.name                                         AS receipt_item_name,
        pr.name,
        pr.supplier_name,
        pr.supplier_delivery_note                        AS delivery_note,
        pr.custom_lot_no                                 AS lot_no,
        pr.posting_date,
        pri.item_code,
        pri.description,
        pri.warehouse,
        -- sle.qty_after_transaction                     AS qty_after_transaction,
        pri.received_qty,
        (pri.received_qty - IFNULL(pri.rejected_qty, 0)) AS accepted_qty,
        IFNULL(pri.rejected_qty, 0)                      AS rejected_qty
    FROM `tabPurchase Receipt` pr
    INNER JOIN `tabPurchase Receipt Item` pri
        ON pri.parent = pr.name
    LEFT JOIN `tabPurchase Order` po
        ON po.name = pri.purchase_order
    -- LEFT JOIN `tabStock Ledger Entry` sle
    --     ON sle.voucher_type      = 'Purchase Receipt'
    --    AND sle.voucher_no        = pr.name
    --    AND sle.voucher_detail_no = pri.name
    --    AND sle.is_cancelled      = 0
    WHERE pr.docstatus = 1
      AND IFNULL(po.is_subcontracted, 0) = 0

    UNION ALL

    -- Subcontracting Receipts
    SELECT
        'Subcontracting'                                   AS receipt_type,
        scri.name                                          AS receipt_item_name,
        scr.name,
        scr.supplier_name,
        scr.supplier_delivery_note                         AS delivery_note,
        scr.custom_lot_no                                  AS lot_no,
        scr.posting_date,
        scri.item_code,
        scri.description,
        scri.warehouse,
        -- sle.qty_after_transaction                       AS qty_after_transaction,
        scri.received_qty,
        (scri.received_qty - IFNULL(scri.rejected_qty, 0)) AS accepted_qty,
        IFNULL(scri.rejected_qty, 0)                       AS rejected_qty
    FROM `tabSubcontracting Receipt` scr
    INNER JOIN `tabSubcontracting Receipt Item` scri
        ON scri.parent = scr.name
    -- LEFT JOIN `tabStock Ledger Entry` sle
    --     ON sle.voucher_type      = 'Subcontracting Receipt'
    --    AND sle.voucher_no        = scr.name
    --    AND sle.voucher_detail_no = scri.name
    --    AND sle.is_cancelled      = 0
    WHERE scr.docstatus = 1
),

billed_purchase_receipts AS (
    SELECT
        pii.purchase_receipt   AS receipt_name,
        pii.pr_detail          AS receipt_item_name,
        SUM(IFNULL(pii.qty, 0)) AS billed_qty
    FROM `tabPurchase Invoice Item` pii
    INNER JOIN `tabPurchase Invoice` pi
        ON pi.name = pii.parent
    WHERE pi.docstatus = 1
      AND IFNULL(pii.purchase_receipt, '') <> ''
      AND IFNULL(pii.pr_detail, '')        <> ''
    GROUP BY
        pii.purchase_receipt,
        pii.pr_detail
),

billed_subcontracting_receipts AS (
    SELECT
        pr.subcontracting_receipt        AS receipt_name,
        pri.subcontracting_receipt_item  AS receipt_item_name,
        SUM(IFNULL(pii.qty, 0))          AS billed_qty
    FROM `tabPurchase Receipt Item` pri
    INNER JOIN `tabPurchase Receipt` pr
        ON pr.name = pri.parent
    INNER JOIN `tabPurchase Invoice Item` pii
        ON pii.pr_detail = pri.name
    INNER JOIN `tabPurchase Invoice` pi
        ON pi.name      = pii.parent
       AND pi.docstatus = 1
    WHERE pr.docstatus = 1
      AND IFNULL(pr.subcontracting_receipt, '')       <> ''
      AND IFNULL(pri.subcontracting_receipt_item, '') <> ''
    GROUP BY
        pr.subcontracting_receipt,
        pri.subcontracting_receipt_item
),

subcontracting_elongation AS (
    SELECT
        se.custom_subcontracting_receipt AS receipt_name,
        sed.item_code,
        SUM(IFNULL(sed.qty, 0))          AS elongation
    FROM `tabStock Entry` se
    INNER JOIN `tabStock Entry Detail` sed
        ON sed.parent = se.name
    WHERE se.docstatus        = 1
      AND se.stock_entry_type = 'Elongation'
      AND IFNULL(se.custom_subcontracting_receipt, '') <> ''
    GROUP BY
        se.custom_subcontracting_receipt,
        sed.item_code
),

-- Number each RM row per (receipt, rm_item) so a supplied row can be
-- paired 1:1 with the corresponding process-loss row of the same rank.
subcontracting_process_loss_supplied_rows AS (
    SELECT
        scr.name              AS receipt_name,
        scri.item_code        AS fg_item_code,
        scrsi.rm_item_code,
        ROW_NUMBER() OVER (
            PARTITION BY scr.name, scrsi.rm_item_code
            ORDER BY
                IFNULL(scri.idx, 0),
                IFNULL(scrsi.idx, 0),
                scrsi.name
        ) AS rm_occurrence
    FROM `tabSubcontracting Receipt` scr
    INNER JOIN `tabSubcontracting Receipt Item` scri
        ON scri.parent = scr.name
    INNER JOIN `tabSubcontracting Receipt Supplied Item` scrsi
        ON scrsi.parent         = scr.name
       AND scrsi.main_item_code = scri.item_code
    WHERE scr.docstatus = 1
),

subcontracting_process_loss_rows AS (
    SELECT
        loss_entry.custom_subcontracting_receipt AS receipt_name,
        loss_detail.item_code                    AS rm_item_code,
        IFNULL(loss_detail.qty, 0)               AS loss_qty,
        ROW_NUMBER() OVER (
            PARTITION BY loss_entry.custom_subcontracting_receipt, loss_detail.item_code
            ORDER BY
                IFNULL(loss_entry.idx, 0),
                IFNULL(loss_detail.idx, 0),
                loss_detail.name
        ) AS rm_occurrence
    FROM `tabStock Entry` loss_entry
    INNER JOIN `tabStock Entry Detail` loss_detail
        ON loss_detail.parent = loss_entry.name
    WHERE loss_entry.docstatus        = 1
      AND loss_entry.stock_entry_type = 'Process Loss'
      AND IFNULL(loss_entry.custom_subcontracting_receipt, '') <> ''
),

subcontracting_process_loss AS (
    SELECT
        supplied.receipt_name,
        supplied.fg_item_code  AS item_code,
        SUM(loss.loss_qty)     AS process_loss
    FROM subcontracting_process_loss_supplied_rows supplied
    INNER JOIN subcontracting_process_loss_rows loss
        ON loss.receipt_name  = supplied.receipt_name
       AND loss.rm_item_code  = supplied.rm_item_code
       AND loss.rm_occurrence = supplied.rm_occurrence
    GROUP BY
        supplied.receipt_name,
        supplied.fg_item_code
)

SELECT
    r.receipt_type,
    r.name,
    r.supplier_name,
    r.delivery_note,
    r.lot_no,
    r.posting_date,
    r.item_code,
    r.description,
    r.received_qty,
    r.accepted_qty,
    r.rejected_qty,
    CASE
        WHEN r.receipt_type = 'Purchase'       THEN IFNULL(bpr.billed_qty, 0)
        WHEN r.receipt_type = 'Subcontracting' THEN IFNULL(bsr.billed_qty, 0)
    END                                                                          AS billed_qty,
    CASE WHEN r.receipt_type = 'Subcontracting' THEN IFNULL(se.elongation, 0)   END AS elongation,
    CASE WHEN r.receipt_type = 'Subcontracting' THEN IFNULL(spl.process_loss, 0) END AS process_loss,
    r.warehouse
    -- , r.qty_after_transaction
FROM receipts r
LEFT JOIN billed_purchase_receipts bpr
    ON bpr.receipt_name      = r.name
   AND bpr.receipt_item_name = r.receipt_item_name
LEFT JOIN billed_subcontracting_receipts bsr
    ON bsr.receipt_name      = r.name
   AND bsr.receipt_item_name = r.receipt_item_name
LEFT JOIN subcontracting_elongation se
    ON se.receipt_name = r.name
   AND se.item_code    = r.item_code
LEFT JOIN subcontracting_process_loss spl
    ON spl.receipt_name = r.name
   AND spl.item_code    = r.item_code
WHERE r.lot_no IS NOT NULL
ORDER BY
    r.posting_date ASC,
    r.name         ASC,
    r.item_code    ASC
    """, as_dict=1)
    return data
frappe.response["message"] = purchase_jobwork_report()