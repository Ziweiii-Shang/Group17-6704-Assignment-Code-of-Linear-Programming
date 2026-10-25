# Original instance workbooks

This directory contains the nine original `.xlsx` workbooks used for the project. They are the source inputs for column generation and can be passed to PTE with `--input data/raw`. The corresponding PTE/heuristic caches are in `../processed/`.

Each workbook has an exactly matching cache basename. Preserve the capitalization in `Large` when specifying a filename.

| Instance family | Small | Middle | Large |
| --- | --- | --- | --- |
| Corridor | `instance_corridor_timewindow_small.xlsx` | `instance_corridor_timewindow_middle.xlsx` | `instance_corridor_timewindow_Large.xlsx` |
| Hub | `instance_hub_timewindow_small.xlsx` | `instance_hub_timewindow_middle.xlsx` | `instance_hub_timewindow_Large.xlsx` |
| Random | `instance_random_timewindow_small.xlsx` | `instance_random_timewindow_middle.xlsx` | `instance_random_timewindow_Large.xlsx` |

SHA-256 checksums below identify the exact source files. They match the `source_sha256` values stored in all nine `../processed/*.input.pkl` caches.

| Workbook | SHA-256 |
| --- | --- |
| `instance_corridor_timewindow_Large.xlsx` | `9cf4d93fec7fc4655c897b8ca16e9bf0cfc984466d98f8aeeba68cabdaf21516` |
| `instance_corridor_timewindow_middle.xlsx` | `f6e3d85ce7c8ebd5440d0d7e96dd0d8a3a9ee1b71417d7fd21fb482fb78e807b` |
| `instance_corridor_timewindow_small.xlsx` | `8debd3f29b6d609016266326a24bd271dd260e3a573883d76267ba42e0d1de3e` |
| `instance_hub_timewindow_Large.xlsx` | `ff3edd7204a1b9b987f985202369bdfd1dfef781c8534d753d86bb5ad7b8ede1` |
| `instance_hub_timewindow_middle.xlsx` | `7a3fec1d6106a451a363334f8bead01ab8f84286d6b05a1bedb4cec70d3fa10e` |
| `instance_hub_timewindow_small.xlsx` | `a22a4932d7152d9eafd28e7833a26e79813e52546d933337b1f6ba0f39d6adcb` |
| `instance_random_timewindow_Large.xlsx` | `e2d1ac503ece706ddcbbf6c0e449f9b13c29b6733a57d47e9ccc11fde814b55c` |
| `instance_random_timewindow_middle.xlsx` | `c5c4d556559eb755aa979517781497c81fe12673c334a0708d14ea929dc4ed81` |
| `instance_random_timewindow_small.xlsx` | `3ecca271024d0770f262c4ee0591e1a6bc2a64be1eb34154ead598eb018d29f7` |

The CG reader requires these sheets and columns:

- `Arcs`: `from_node`, `to_node`, `capacity`, `travel_time`.
- `Commodities`: `commodity`, `origin`, `destination`, `demand`, `release_time`, `latest_arrival`, `max_travel_time`.
- `Costs`: `commodity`, `from_node`, `to_node`, `cost`.

`latest_arrival - release_time` must equal `max_travel_time`.
