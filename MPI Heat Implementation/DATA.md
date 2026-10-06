# Data

No external data is used. Every input is generated at run time by
`src/heatgrid/core/scenarios.py` from a scenario name and a seed, so there is
nothing to download and no licence to worry about.

| Scenario            | Seed | What it is |
|---------------------|------|------------|
| `uniform`           | 1001 | flat 0.5 interior, 0.3 boundary |
| `single_hotspot`    | 2001 | one Gaussian hotspot near the centre |
| `multiple_hotspots` | 3001 | four Gaussian hotspots |
| `gradient`          | 4001 | linear ramp in x and y |
| `decaying_sine`     | 5001 | sin(pi x) sin(pi y), has an exact solution, used in tests |

Seeds go into `numpy.random.default_rng`, so the same name and seed always give
the same field on any machine. Pass `--seed` to `src/heat.py` to change one.

The scenarios are loosely based on the kinds of temperature patterns reported
for Johannesburg (one heat island, several hotspots, a north-south gradient).
They are **not** measured temperatures, and none of the results say anything
about the real climate. They only exist to check whether the thermal pattern
changes performance (it shouldn't, the stencil does the same work everywhere).

There is no preprocessing. `fig_scenario_fields` in `paper/figures/` shows
what each field looks like before and after diffusion.
