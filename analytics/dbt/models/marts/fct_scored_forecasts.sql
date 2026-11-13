-- Every resolved forecast with its clipped Brier term (probabilities clipped to [0.01, 0.99]).
select
    q.question_id,
    q.domain,
    q.batch_date,
    f.forecaster_id,
    f.probability,
    r.outcome,
    power(least(greatest(f.probability, 0.01), 0.99) - r.outcome, 2) as brier
from {{ ref('stg_forecasts') }} as f
join {{ ref('stg_resolutions') }} as r using (question_id)
join {{ ref('stg_questions') }} as q using (question_id)
