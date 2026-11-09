# Mathematical model

This document describes the mixed-integer programs solved by `distnet`. Notation:

| Symbol | Meaning |
|---|---|
| $F$, $S$, $C$, $K$ | facilities, service areas, carriers, construction crews |
| $T = \{0,\dots,H-1\}$ | periods of the planning horizon (levels 4–5) |
| $cap_f$, $o_f$ | capacity (per period) and one-time opening cost of facility $f$ |
| $d_s$ (or $d_{s,t}$) | demand of service area $s$ (in period $t$) |
| $p_s$ | unit selling price in service area $s$ |
| $c_{fs}$ | base unit shipping cost from $f$ to $s$ |
| $m_{cs}$ | multiplier of carrier $c$ on area $s$ (only defined if $c$ serves $s$) |
| $V_c$ | maximum total volume of carrier $c$ |
| $b_f$ | build time of facility $f$ (periods) |
| $B$ | budget |

Shipping is **never forced**: demand constraints are upper bounds, so the model decides
which demand is worth serving.

---

## Levels 1–3: static facility location (`distnet.static`)

Variables: $x_{fsc}\in\mathbb Z_{\ge 0}$ units shipped from $f$ to $s$ via carrier $c$
(for level 1–2 there is a single implicit "direct" carrier with $m=1$ and no volume limit),
and $y_f\in\{0,1\}$ = facility $f$ is opened.

$$
\max \sum_{f,s,c} \bigl(p_s - m_{cs}\,c_{fs}\bigr)\,x_{fsc} \;-\; \sum_f o_f\,y_f
$$

subject to

$$
\begin{aligned}
&\sum_{s,c} x_{fsc} \le cap_f\,y_f && \forall f &&\text{(capacity, only if open)}\\
&\sum_{f,c} x_{fsc} \le d_s && \forall s &&\text{(demand)}\\
&\sum_{f,s} x_{fsc} \le V_c && \forall c &&\text{(carrier fleet)}\\
&\sum_{f,s,c} m_{cs}\,c_{fs}\,x_{fsc} + \sum_f o_f\,y_f \le B &&&&\text{(budget)}
\end{aligned}
$$

The budget covers shipping and opening costs, not revenue. This is why the budget is the
binding constraint in every bundled instance and why the problem behaves like a knapsack.

### Strengthening (default, `--no-strengthen` to disable)

Linking inequalities, valid for every integer solution:

$$
x_{fsc} \le \min(cap_f,\; d_s,\; V_c)\; y_f \qquad \forall f,s,c
$$

In the LP relaxation the capacity constraint alone lets a facility be "partly open"
($y_f = $ load $/ cap_f$) so the relaxation is very optimistic. The linking constraints
cut that off. They never remove an integer-feasible solution, so the optimum is unchanged.

### Pruning (default, `--no-prune` to disable)

An arc $(f,s,c)$ with $p_s \le m_{cs}c_{fs}$ (loses money), or with $d_s=0$ or
$cap_f=0$, can never improve the objective while it always consumes budget, so its variable
is not created.

---

## Levels 4–5: multi-period model with construction (`distnet.scheduling`)

Facilities must be built before they can ship. A job occupies one crew for $b_f$
consecutive periods; a crew can only work on one facility at a time; everything has to be
finished inside the horizon.

Variables: $x_{fst}\in\mathbb Z_{\ge0}$ shipments, $y_f\in\{0,1\}$ built, and
$z_{ft}\in\{0,1\}$ = construction of $f$ **starts** in period $t$ (only for
$t + b_f \le H$).

$$
\max \sum_{f,s,t}(p_s - c_{fs})\,x_{fst} - \sum_f o_f\,y_f
$$

$$
\begin{aligned}
&\sum_{t} z_{ft} = y_f && \forall f &&\text{(built once iff opened)}\\
&\sum_{f}\ \sum_{t'\,:\,t'\le t< t'+b_f} z_{ft'} \le |K| && \forall t &&\text{(crews)}\\
&\sum_s x_{fst} \le cap_f \sum_{t'\le t-b_f} z_{ft'} && \forall f,t &&\text{(ship only when completed)}\\
&\sum_f x_{fst} \le d_{s,t} && \forall s,t &&\text{(period demand)}\\
&\sum_{\tau\le t} z_{g\tau} \le \sum_{\tau \le t-b_f} z_{f\tau} && \forall (f,g)\in D,\ t &&\text{(precedence)}\\
&\sum_{f,s,t} c_{fs}\,x_{fst} + \sum_f o_f\,y_f \le B &&&&\text{(budget)}
\end{aligned}
$$

### Crew symmetry removed

The crews are interchangeable. Indexing $z$ by crew, as in the textbook model $z_{fct}$,
creates $|K|!$ equivalent solutions for every schedule, which a branch-and-bound solver has to
explore. Instead the model only limits *how many* jobs run at the same time. Afterwards
the jobs are assigned to named crews by greedy interval colouring
(`distnet.scheduling.assign_crews`). Interval graphs are perfect, so whenever at most
$|K|$ jobs overlap at any time this always succeeds, and the result is a valid per-crew
schedule. The textbook model is still available (`--crew-model indexed`) for cross-checking.

### Time-indexed precedence

For a dependency $(f,g)$ ("$g$ can only start after $f$ is completed, and only if $f$ is built") the
original model used a big-M constraint
$\text{completion}_f \le \text{start}_g + H(1-y_g)$ together with $y_g\le y_f$.
The constraint above says "if $g$ has started by $t$, then $f$ was completed by $t$" for every
$t$. It is equivalent on integer points, needs no big-M, has a tighter LP relaxation, and
already implies $y_g\le y_f$ (take $t=H-1$).

### Variable reduction

Facility $f$ cannot ship before period $b_f$, so $x_{fst}$ for $t<b_f$ is not created. Start
variables only exist for starts that can finish within the horizon, which makes the
"finish in time" constraint of the original model unnecessary.

### Linking cuts

$$
x_{fst} \le \min(cap_f,\ d_{s,t}) \sum_{t'\le t-b_f} z_{ft'}
$$

Measured LP-relaxation gap to the optimum (relaxing all integrality, same model otherwise):

| Instance | without cuts | with cuts |
|---|---|---|
| level 1 | 1.76 % | 1.76 % |
| level 3_2 | 3.45 % | 3.14 % |
| level 4 | 8.50 % | **0.26 %** |
| level 5 | 0.14 % | 0.11 % |

---

## Verification

`distnet.verify` re-derives every constraint from the raw instance data without touching
any solver code: capacities, demands, carrier volumes, budget, crew overlaps, completion
before shipping, dependencies, and the reported revenue / cost totals. The CLI runs it after
every solve, and the test-suite uses it as an oracle.
