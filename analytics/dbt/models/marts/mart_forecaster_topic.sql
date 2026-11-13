-- Mean Brier score per forecaster and topic (display only; intervals are on the site).
select
    forecaster_id,
    domain,
    count(*) as n,
    avg(brier) as brier
from {{ ref('fct_scored_forecasts') }}
group by forecaster_id, domain
