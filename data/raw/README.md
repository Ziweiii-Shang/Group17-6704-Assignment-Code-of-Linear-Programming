# Original instance workbooks

The supplied materials contain nine validated pickle caches, but no original `.xlsx` workbooks. Heuristics read `../processed/`; column generation requires the original Excel files here (or an explicit path through `--input`). Do not rename caches to Excel files.

The CG reader requires these sheets and columns:

- `Arcs`: `from_node`, `to_node`, `capacity`, `travel_time`.
- `Commodities`: `commodity`, `origin`, `destination`, `demand`, `release_time`, `latest_arrival`, `max_travel_time`.
- `Costs`: `commodity`, `from_node`, `to_node`, `cost`.

`latest_arrival - release_time` must equal `max_travel_time`.
