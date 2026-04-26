WITH open_order AS (
  -- distinct shipment/production pairs used to filter stock ledger
  SELECT DISTINCT shipment_id, production
  FROM `openbridge-bigquery-data.encasa_openbridge.calc_erp_sales_order`
),

stock_ledger AS (
  /*
   Aggregate dispatched qty from stock ledger for matching shipment/production
   Note: join uses SUBSTR(oo.shipment_id,1,6) = SUBSTR(sle.remarks,1,6) to match by a shared prefix.
   This produces a positive 'dispatch_from_stock' value by summing -actual_qty where actual_qty < 0.
  */
  SELECT
    oo.shipment_id,
    oo.production,
    sle.item_code,
    SUM(-sle.actual_qty) AS dispatch_from_stock  -- convert negative actual_qty to positive dispatched quantity
  FROM `openbridge-bigquery-data.encasa_openbridge.calc_erp_stock_ledger` AS sle
  JOIN open_order AS oo
    ON SUBSTR(oo.shipment_id, 1, 6) = SUBSTR(sle.remarks, 1, 6)
    AND oo.production = sle.branch
  WHERE sle.voucher_type = 'Stock Entry'
    AND sle.actual_qty < 0
  GROUP BY oo.shipment_id, oo.production, sle.item_code
)

SELECT
  -- identifiers & attributes
  oi.channel_abb,
  oi.shipment_id AS po_no,         -- PO / shipment identifier
  oi.etd AS dispatch_date,        -- expected dispatch date
  oi.production,                   -- branch / production
  oi.sku,                          -- ordered SKU
  sm.line,                         -- product attribute (mapping)
  sm.color,
  sm.size,
  sm.pcs_pack,
  sm.product,

  -- raw order & fulfillment fields from sales order / fulfillment / stock ledger
  oi.po_qty,                       -- ordered quantity (header)
  oi.dispatched_qty,               -- quantity dispatched against the order

  -- dispatch_from_stock from aggregated stock_ledger (coerce null -> 0)
  COALESCE(SAFE_CAST(sl.dispatch_from_stock AS NUMERIC), CAST(0 AS NUMERIC)) AS dispatch_from_stock,

  oi.pending_qty,                  -- pending quantity on the order

  -- allocated_from_stock and to_produce_qty from order fulfillment (coerce null -> 0)
  COALESCE(SAFE_CAST(ofs.allocated_from_stock AS NUMERIC), CAST(0 AS NUMERIC)) AS allocated_from_stock,
  COALESCE(SAFE_CAST(ofs.to_produce_qty AS NUMERIC), CAST(0 AS NUMERIC)) AS to_produce_qty,

  -- BOM / raw material identifiers (finalized)
  -- If bom_status = 'No-Need' we use the SKU itself as the "raw material code" (e.g. flexible items)
  CASE WHEN bs.bom_status = 'No-Need' THEN oi.sku ELSE bei.raw_material_code END AS raw_material_code,
  CASE WHEN bs.bom_status = 'No-Need' THEN 'No-Need' ELSE bei.bom_id END AS bom_id,

  -- description: if No-Need -> take description from item master row for the SKU (rm_no),
  -- otherwise take description from BOM explosion item (bei)
  CASE
    WHEN bs.bom_status = 'No-Need' THEN rm_no.description
    ELSE bei.description
  END AS description,

  -- quality: if No-Need -> from the SKU's item master row (rm_no.quality),
  -- else from the raw material's item master row (rm.quality)
  CASE
    WHEN bs.bom_status = 'No-Need' THEN rm_no.quality
    ELSE rm.quality
  END AS quality,

  -- final cons_per_unit (numeric): for No-Need use product.pcs_pack, else BOM cons_per_unit
  COALESCE(
    CASE WHEN bs.bom_status = 'No-Need' THEN SAFE_CAST(sm.pcs_pack AS NUMERIC)
         ELSE SAFE_CAST(bei.cons_per_unit AS NUMERIC)
    END,
    CAST(0 AS NUMERIC)
  ) AS cons_per_unit,

  -- material_type classification:
  --  - 'Raw Material' when code(s) start with 'FA-' (flex/fabric) either for SKU or raw_material_code
  --  - 'Semi-finished goods' when either No-Need or bei.raw_material_code exists (fallback)
  --  - 'unknown' otherwise
  CASE
    WHEN (
      (bs.bom_status = 'No-Need' AND oi.sku IS NOT NULL AND STARTS_WITH(UPPER(oi.sku), 'FA-'))
      OR (bei.raw_material_code IS NOT NULL AND STARTS_WITH(UPPER(bei.raw_material_code), 'FA-'))
    ) THEN 'Raw Material'
    WHEN (bs.bom_status = 'No-Need' OR bei.raw_material_code IS NOT NULL) THEN 'Semi-finished goods'
    ELSE 'unknown'
  END AS material_type,

  -- need_type: business classification used downstream (labels as in your source logic)
  CASE
    WHEN oi.sku IS NOT NULL AND STARTS_WITH(UPPER(oi.sku), 'FA-') THEN 'Need for flex'
    WHEN (
      (bei.raw_material_code IS NOT NULL AND STARTS_WITH(UPPER(bei.raw_material_code), 'FA-'))
      OR (bs.bom_status = 'No-Need' AND STARTS_WITH(UPPER(oi.sku), 'FA-'))
    ) THEN 'For Production'
    ELSE 'For Assembly'
  END AS need_type,

  -- required_qty: quantity required now (depends on No-Need flag)
  CASE
    WHEN bs.bom_status = 'No-Need' THEN COALESCE(SAFE_CAST(oi.pending_qty AS NUMERIC), CAST(0 AS NUMERIC))
    ELSE (
      COALESCE(SAFE_CAST(ofs.to_produce_qty AS NUMERIC), CAST(0 AS NUMERIC))
      *
      COALESCE(SAFE_CAST(bei.cons_per_unit AS NUMERIC), CAST(0 AS NUMERIC))
    )
  END AS required_qty,

  -- consumed_qty:
  -- (dispatched_qty - dispatch_from_stock) * cons_per_unit
  (
    COALESCE(SAFE_CAST(oi.dispatched_qty AS NUMERIC), CAST(0 AS NUMERIC))
    - COALESCE(SAFE_CAST(sl.dispatch_from_stock AS NUMERIC), CAST(0 AS NUMERIC))
  ) *
  (
    COALESCE(
      CASE WHEN bs.bom_status = 'No-Need' THEN SAFE_CAST(sm.pcs_pack AS NUMERIC)
           ELSE SAFE_CAST(bei.cons_per_unit AS NUMERIC)
      END,
      CAST(0 AS NUMERIC)
    )
  ) AS consumed_qty,

  -- initial_required_qty:
  -- If No-Need: pending_qty
  -- Else: (po_qty - dispatch_from_stock - allocated_from_stock) * cons_per_unit
  CASE
    WHEN bs.bom_status = 'No-Need' THEN COALESCE(SAFE_CAST(oi.pending_qty AS NUMERIC), CAST(0 AS NUMERIC))
    ELSE (
      (
        COALESCE(SAFE_CAST(oi.po_qty AS NUMERIC), CAST(0 AS NUMERIC))
        -- - COALESCE(SAFE_CAST(sl.dispatch_from_stock AS NUMERIC), CAST(0 AS NUMERIC))
        -- - COALESCE(SAFE_CAST(ofs.allocated_from_stock AS NUMERIC), CAST(0 AS NUMERIC))
      )
      *
      COALESCE(SAFE_CAST(bei.cons_per_unit AS NUMERIC), CAST(0 AS NUMERIC))
    )
  END AS initial_required_qty

FROM `openbridge-bigquery-data.encasa_openbridge.calc_erp_sales_order` oi

-- whether SKU is manufactured; used in WHERE to filter only manufactured or No-Need SKUs
LEFT JOIN (
  SELECT sku, is_manufactured
  FROM `openbridge-bigquery-data.encasa_openbridge.calc_erp_item_master`
) im
  ON oi.sku = im.sku

-- sku -> sku mapping for product attributes (line, color, size, pcs_pack, product)
LEFT JOIN `openbridge-bigquery-data.encasa_openbridge.calc_sku_mapping` sm
  ON oi.sku = sm.sku

-- BOM status (No-Need, etc.) - moved before bei join to enable filtering
LEFT JOIN `openbridge-bigquery-data.encasa_openbridge.calc_erp_bom_status` bs
  ON oi.sku = bs.sku

-- BOM explosion items (may produce multiple rows per SKU for multi-component BOMs)
-- Only join bei for SKUs that are NOT 'No-Need' to avoid duplicates for No-Need items
LEFT JOIN `openbridge-bigquery-data.encasa_openbridge.calc_erp_bom_explosion_item` bei
  ON oi.sku = bei.sku
  AND (bs.bom_status IS NULL OR bs.bom_status != 'No-Need')

-- item master row for the raw material (bei.raw_material_code)
LEFT JOIN `openbridge-bigquery-data.encasa_openbridge.calc_erp_item_master` rm
  ON bei.raw_material_code = rm.sku

-- item master row for the SKU itself (used when bom_status = 'No-Need')
LEFT JOIN `openbridge-bigquery-data.encasa_openbridge.calc_erp_item_master` rm_no
  ON oi.sku = rm_no.sku

-- order fulfillment summary (allocated_from_stock, to_produce_qty)
LEFT JOIN `openbridge-bigquery-data.encasa_openbridge.calc_erp_order_fulfillment` ofs
  ON oi.shipment_id = ofs.shipment_id
  AND oi.sku = ofs.sku

-- stock ledger aggregated data (dispatch_from_stock)
LEFT JOIN stock_ledger sl
  ON oi.shipment_id = sl.shipment_id
  AND oi.sku = sl.item_code

-- only include manufactured SKUs OR SKUs with bom_status = 'No-Need'
WHERE (im.is_manufactured = TRUE) OR (bs.bom_status = 'No-Need')