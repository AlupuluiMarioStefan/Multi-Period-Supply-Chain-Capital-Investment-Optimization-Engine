# distnet — Distribution Network Optimization

[![CI](https://github.com/AlupuluiMarioStefan/Multi-Period-Supply-Chain-Capital-Investment-Optimization-Engine/actions/workflows/ci.yml/badge.svg)](https://github.com/AlupuluiMarioStefan/Multi-Period-Supply-Chain-Capital-Investment-Optimization-Engine/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Profit-maximising **distribution network design** with mixed-integer linear programming
([PuLP](https://github.com/coin-or/pulp) + CBC). Decide which facilities to open, how much
to ship from where to whom, which carriers to use, and when to build facilities — all under a
budget.

The project grew from a five-part optimisation course assignment. Each part adds one
real-world complication to the previous one, and all of them now run through one small,
tested package with a CLI.

## Problem levels

| Level | What is added | Instances |
|---|---|---|
| **1** | Open facilities (fixed cost, capacity), ship to service areas (price, demand), stay within budget | `data/level1.json` |
| **2** | Same model, loaded from text files | `data/level2_1`, `data/level2_2` |
| **3** | **Carriers**: each serves only some areas, with a price multiplier per area and a total volume limit | `data/level3_1`, `data/level3_2` |
| **4** | **Time**: facilities take several periods to build, a limited number of **crews** build one facility at a time, shipping only starts after completion | `data/level4.json` |
| **5** | **Seasonal demand** and **dependencies** between facilities (B can only be built after A is finished) | `data/level5.json` |

Levels 1–3 are solved by one static model (`distnet.static`), levels 4–5 by one scheduling
model (`distnet.scheduling`). The full formulation is in [docs/MODEL.md](docs/MODEL.md).

## Installation

```bash
git clone https://github.com/AlupuluiMarioStefan/Multi-Period-Supply-Chain-Capital-Investment-Optimization-Engine.git
cd Multi-Period-Supply-Chain-Capital-Investment-Optimization-Engine
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

The only runtime dependency is `pulp` (it bundles the CBC solver). Nothing needs to be
pinned: the package avoids `LpVariable.dicts`, which was the cause of the PuLP 4.0 problems
in the original scripts.

## Usage

### Command line

```bash
distnet solve data/level3_1                  # text-file instance (a directory)
distnet solve data/level5.json               # JSON instance
distnet solve data/level5.json --time-limit 120 --gap 0.01
distnet solve data/level3_2 --json out.json --csv plan.csv
distnet validate my_instance.json            # check a file without solving
python -m distnet solve data/level1.json     # same thing without installing the script
```

Example output (level 5, abridged):

```
Status:          Optimal
Total profit:    99,169
  revenue 116,169 - opening 2,130 - shipping 14,870
Budget used:     17,000 / 17,000 (100.00%)
Facilities open: F1, F2, F3, F6, F7, F8, F9, F10

Crew timeline (. = idle):
      0   1   2   3   4   5   6   7 ...
  K1  F1  F1  F1  F2  F2  F3  .   . ...
  K2  F10 F9  F9  .   .   F8  .   . ...
  K3  F6  F6  F7  F7  F7  .   .   . ...

Independent verification: PASSED
```

The exit code is `0` only if the solution is optimal **and** passes the independent verifier.

| Option | Meaning |
|---|---|
| `--time-limit SEC` / `--gap REL` | solver limits for large instances |
| `--no-strengthen` | omit the valid linking inequalities (slower, same optimum) |
| `--no-prune` | keep variables for unprofitable lanes |
| `--crew-model indexed` | use the textbook per-crew formulation (scheduling only) |
| `--json FILE` / `--csv FILE` | export the full solution / allocation plan |
| `--solver-log` | show the CBC log |

### Python API

```python
from distnet import load_instance, solve, verify, format_report

instance = load_instance("data/level3_1")
solution = solve(instance, time_limit=60)

print(solution.total_profit, solution.facilities_opened)
print(format_report(instance, solution))
assert verify(instance, solution) == []
```

You can also build instances directly in code
([examples/build_instance_in_code.py](examples/build_instance_in_code.py)) or plug in another
PuLP solver: `solve(instance, solver=pulp.HiGHS())`.

## Input formats

**Text directory** (levels 2–3) containing `facilities.txt`, `service_areas.txt`,
`budget.txt` and optionally `carriers.txt`; all `;`-separated with a header line:

```
facilities.txt   facility;capacity;opening_cost;shipping_costs
                 F1;800;450;{'S1': 4, 'S2': 3, ...}
service_areas    service_area;demand;unit_selling_price
carriers.txt     carrier;max_volume;area_multipliers
                 C1;500;[('S1', 0.9), ('S2', 1.1), ...]
budget.txt       budget
                 6000
```

Dictionary and list columns are parsed with `ast.literal_eval` (not `eval`), so a data file
can never execute code.

**JSON** (all levels), `"type": "static"` or `"scheduling"`. Scheduling instances accept a
constant `demand` per area, an explicit per-period list, or a base demand plus
`seasonal_factors` (see `data/level5.json`):

```json
{
  "type": "scheduling", "budget": 17000, "horizon": 15, "crews": ["K1", "K2", "K3"],
  "seasonal_factors": [0.6, 0.8, 1.3, ...],
  "facilities": {"F1": {"capacity": 70, "opening_cost": 300, "build_time": 3,
                        "shipping_cost": {"S1": 6, "S2": 3, ...}}, ...},
  "service_areas": {"S1": {"demand": 90, "price": 15}, ...},
  "dependencies": [["F1", "F2"], ["F2", "F3"]]
}
```

Instances are validated on load (missing costs, negative values, unknown ids, ...) and
raise `InstanceError` with a message that says what is wrong.

## Results

Optimal solutions for the bundled instances (identical to the original course scripts):

| Instance | Profit | Facilities opened | Demand served |
|---|---:|---|---:|
| level1 | 19,792 | F1 F2 F3 | 69.0 % |
| level2_1 | 20,729 | F4 F5 F6 | 40.7 % |
| level2_2 | 26,604 | F1 F3 F5 F7 F8 | 45.7 % |
| level3_1 | 23,692.15 | F1 F2 F5 F6 | 51.2 % |
| level3_2 | 30,807.15 | F1 F3 F5 F6 F7 F8 | 54.1 % |
| level4 | 23,160 | F1 F2 F4 F5 | 50.0 % |
| level5 | 99,169 | F1 F2 F3 F6 F7 F8 F9 F10 | 57.2 % |

In every instance the budget is fully used: the budget (shipping + opening costs, not
revenue) is what limits profit, not demand.

## What is improved compared to the original scripts

| Area | Before | Now |
|---|---|---|
| Structure | five copy-pasted scripts, one class each | one package: models, loaders, two solvers, verifier, report, CLI |
| Data loading | `pandas` + `eval()` on file contents | stdlib parsing + `ast.literal_eval`, validation with clear errors |
| PuLP version | needed a downgrade to 3.3.2 for `LpVariable.dicts` | no `dicts`, works with current PuLP |
| Numerical noise | values like `3.69e-13` or `249.9999` leaked into plans | all quantities are rounded integers; totals are recomputed from them |
| Crew modelling | crew-indexed binaries (`K!` symmetric schedules) | aggregated start variables + exact crew assignment afterwards |
| Precedence | big-M | time-indexed constraints (tighter, implies the opening link) |
| Formulation | capacity-only linking | valid linking cuts + removal of useless variables (≈30 % fewer variables on level 5) |
| Checking | print statements | independent verifier (`distnet.verify`) used by CLI and tests |
| Output | prints in the module body | `format_report`, JSON and CSV export, crew timeline |
| Quality | none | 20 tests, GitHub Actions CI, documented model |

All optimisations are switchable (`--no-strengthen`, `--no-prune`, `--crew-model indexed`)
and the tests assert that they never change the optimal value.

## Repository layout

```
.
├── src/distnet/
│   ├── models.py       # instances, solutions, validation
│   ├── io.py           # text/JSON loaders, JSON/CSV writers
│   ├── static.py       # levels 1-3 model
│   ├── scheduling.py   # levels 4-5 model, crew assignment
│   ├── verify.py       # solver-independent feasibility checker
│   ├── report.py       # text report, crew timeline
│   └── cli.py          # `distnet` command
├── data/               # bundled instances (levels 1-5)
├── tests/              # unittest/pytest suite
├── docs/MODEL.md       # mathematical formulation
├── examples/           # API examples
└── legacy/             # the original course scripts, unchanged
```

## Development

```bash
pip install -e ".[dev]"
pytest                    # full suite
```

To add an instance, drop a JSON file or a directory into `data/`, run
`distnet validate <path>` and then `distnet solve <path>`.

Large instances can take a while with CBC. Use `--time-limit` and `--gap` to trade
optimality for speed, or pass a different solver through the Python API.

## License

[MIT](LICENSE). 
