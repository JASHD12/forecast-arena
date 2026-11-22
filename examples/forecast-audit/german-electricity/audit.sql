-- A second, independent calculation of the audit in SQL (DuckDB), read-only over the two CSV files.
-- Run from this directory:  duckdb -c ".read audit.sql"   (or through the Python test).
-- Costs: a false alert costs 1, a miss costs 4; alert when p >= 1 / (1 + 4) = 0.20 (ties alert).
-- Missing predictions fall back to "no alert". Brier is compared on cases where both models are on time.
WITH params AS (SELECT 1.0 AS fa, 4.0 AS miss, 0.2 AS cutoff),
cases AS (
    SELECT case_id, CAST(group_day AS DATE) AS day, CAST(lock_at AS TIMESTAMPTZ) AS lock_at,
           outcome_state, TRY_CAST(NULLIF(outcome, '') AS INTEGER) AS y
    FROM read_csv('cases.csv', header = true, all_varchar = true)
),
preds AS (
    SELECT case_id, model_id, status, TRY_CAST(NULLIF(probability, '') AS DOUBLE) AS p,
           TRY_CAST(NULLIF(issued_at, '') AS TIMESTAMPTZ) AS issued_at
    FROM read_csv('predictions.csv', header = true, all_varchar = true)
),
models AS (SELECT DISTINCT model_id FROM preds),
grid AS (
    SELECT c.case_id, c.y, m.model_id, p.p,
           (p.status = 'forecast' AND p.issued_at < c.lock_at) AS on_time
    FROM cases c CROSS JOIN models m
    LEFT JOIN preds p ON p.case_id = c.case_id AND p.model_id = m.model_id
    WHERE c.outcome_state = 'resolved'
),
decisions AS (
    SELECT g.model_id AS policy, g.y,
           COALESCE(g.on_time AND g.p >= (SELECT cutoff FROM params), FALSE) AS alert
    FROM grid g
    UNION ALL SELECT 'always_alert', y, TRUE FROM cases WHERE outcome_state = 'resolved'
    UNION ALL SELECT 'never_alert', y, FALSE FROM cases WHERE outcome_state = 'resolved'
),
policy AS (
    SELECT policy,
           COUNT(*) AS cases,
           SUM(CASE WHEN alert THEN 1 ELSE 0 END) AS alerts,
           SUM(CASE WHEN alert AND y = 0 THEN 1 ELSE 0 END) AS false_alerts,
           SUM(CASE WHEN NOT alert AND y = 1 THEN 1 ELSE 0 END) AS misses
    FROM decisions GROUP BY policy
),
shared AS (
    SELECT case_id FROM grid GROUP BY case_id HAVING MIN(CAST(on_time AS INTEGER)) = 1
),
brier AS (
    SELECT g.model_id AS policy, AVG((g.p - g.y) * (g.p - g.y)) AS brier
    FROM grid g JOIN shared s USING (case_id) GROUP BY g.model_id
)
SELECT pol.policy, pol.cases, pol.alerts, pol.false_alerts, pol.misses,
       pol.false_alerts * (SELECT fa FROM params) + pol.misses * (SELECT miss FROM params) AS total_loss,
       b.brier
FROM policy pol LEFT JOIN brier b USING (policy)
ORDER BY pol.policy;
