-- Mean Brier score per forecaster and batch day.
select
    batch_date,
    forecaster_id,
    count(*) as n,
    avg(brier) as brier
from {{ ref('fct_scored_forecasts') }}
group by batch_date, forecaster_id
