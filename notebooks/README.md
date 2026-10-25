# Context Is the Team: workshop notebooks

Two short lessons in **ontology-driven development**: make the domain explicit,
use it to guide code, and check the consequences with named counterexamples.

| Notebook | Question | Domain knowledge that determines the implementation |
|---|---|---|
| [1. A river reading](01_river_reading.ipynb) | Can we compare this reading with this threshold? | Gauge, quantity, datum, units and time |
| [2. One person isn't one row](02_one_person_one_count.ipynb) | How many people completed a degree at this institution? | Identity, relationship cardinality, cohort and reporting unit |

**Start by reading each ontology, not by fixing the code.** Identify the things,
relationships, vocabulary, rules and rationale. Predict a counterexample. Then
give that context to your preferred agent, or implement the function yourself.
Reference implementations and saved outputs are included for an offline walkthrough.

## Open and run

- [Open river notebook in Colab](https://colab.research.google.com/github/MuddyBootsCode/muddybootscode-odscai-2026/blob/codex/workshop-notebooks/notebooks/01_river_reading.ipynb)
- [Open people-count notebook in Colab](https://colab.research.google.com/github/MuddyBootsCode/muddybootscode-odscai-2026/blob/codex/workshop-notebooks/notebooks/02_one_person_one_count.ipynb)

Colab requires internet and a Google session. The notebook code itself needs no
network, API key, paid model, external dataset or extra Python package.
You can also download either `.ipynb` by itself and open it in an existing Jupyter environment.
GitHub displays the saved outputs without running the code.

For local Jupyter, use Python 3.10 or newer. From the repository root:

```bash
python3 -m venv .venv-notebooks
source .venv-notebooks/bin/activate
python -m pip install -r notebooks/requirements.txt
python -m jupyter lab notebooks
```

On Windows activate with `.venv-notebooks\Scripts\activate` instead.
Select **Restart Kernel and Run All Cells** for a clean walkthrough. The faulty
candidate reports expected failures as data; execution then continues to the
reference repair. To practice, stop before the reference repair, add a code cell
with your implementation and pass it to the lesson's `check_*_rules` function.
Keep the domain and checks fixed during a repair.

## What this demonstrates

Each notebook embeds the canonical [river](ontology/river.md) or
[higher-education](ontology/higher_education.md) ontology with a content hash.
The ontology identifies why a function needs particular logic. Named counterexamples
show whether a candidate obeys those rules. The source files link the rules to
the implementation and repository tests.

The higher-ed fixture yields **5 joined profile rows, 2 people and 3 completed
degrees**. Each number has a different meaning. Employment records must not
change the number of graduates. The river fixture's 2.4 meters exceeds the
invented 7-foot comparison threshold after conversion; wrong context yields
**unavailable**, which is distinct from **below**.

Reference mistakes and repairs are authored teaching examples, not reported agent
runs. To investigate the effect of ontology context on your agent, use the
[controlled comparison instructions](FACILITATOR.md). Record actual outcomes,
including when both candidates succeed. These examples alone do not establish
causal model improvements, complete test coverage or an enforced release policy.

## Check or maintain the lessons

Behavioral tests require only Python's standard library:

```bash
python3 -m unittest discover -s notebooks/tests -v
python3 notebooks/build.py --check
```

Edit `lessons/*.py` (percent-cell Python) and `ontology/*.md`, then regenerate
and execute in fresh kernels using the Jupyter environment above:

```bash
python notebooks/build.py --execute
python notebooks/build.py --check
```

Execution uses an empty temporary directory, so it catches accidental dependencies
on local repository files. `build.py` without flags rebuilds without saved outputs;
run `--execute` before publishing. No ontology hook, mod, CI requirement or branch
protection is installed by these notebooks.

The existing [ontology skill and observer](../README.md) remain separate tools for
bringing domain context and checks into a repository workflow.
