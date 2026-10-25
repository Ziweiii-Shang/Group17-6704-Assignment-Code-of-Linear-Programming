# Original instance workbooks

The original `.xlsx` workbooks are not included. Nine validated pickle caches are stored in `../processed/` for the heuristics and PTE-LP. Column generation requires an authorized workbook copy.

The CG reader requires these sheets and columns:

- `Arcs`: `from_node`, `to_node`, `capacity`, `travel_time`.
- `Commodities`: `commodity`, `origin`, `destination`, `demand`, `release_time`, `latest_arrival`, `max_travel_time`.
- `Costs`: `commodity`, `from_node`, `to_node`, `cost`.

`latest_arrival - release_time` must equal `max_travel_time`.
