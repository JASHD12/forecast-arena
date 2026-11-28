# GDELT article-list fixture

One real response of `https://api.gdeltproject.org/api/v2/doc/doc` (`mode=artlist&format=json`, query `bitcoin sourcelang:english`,
20 records, 2026-11-20), recorded on 2026-11-27 at about 22:56 UTC by `scripts/record_gdelt_titles.py` in the `gdelt-titles-record`
workflow. The body is unmodified (`provenance.json` has its SHA-256; a test checks it). It holds titles, outlets, URLs and times
only (S7); the parser keeps only the titles. Some records are not about Bitcoin's price at all: GDELT matches the query words anywhere.

Data: GDELT Project (https://www.gdeltproject.org/).
