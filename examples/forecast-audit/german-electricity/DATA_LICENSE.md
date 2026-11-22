# Licences of the shipped data

- **Code** in this directory is under the repository's MIT licence (`../../../LICENSE`).
- **`cases.csv` and `predictions.csv`** are derived from market data of the Bundesnetzagentur
  ("Bundesnetzagentur | SMARD.de", CC BY 4.0 under https://www.smard.de/home/datennutzung, read on 2026-11-22)
  and from this project's own forecasts. They hold only a yes/no event per delivery day and two
  probabilities; **no hourly prices are shipped**. Use them under CC BY 4.0 and name the source
  "Bundesnetzagentur | SMARD.de" and this repository.
- The SMARD page says the licensing of wholesale prices is under review (HEDWIG procedure). Check the page
  again before redistributing; if it changes, the documented rebuild (`build_case.py`) and the four-case
  example in `../` remain.
- The four-case example in `../` is original illustrative data with no external source.
