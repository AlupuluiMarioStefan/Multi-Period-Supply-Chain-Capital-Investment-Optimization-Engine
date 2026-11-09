# Legacy course scripts

These are the original, self-contained assignment submissions (`1.py` ... `5.py`) with
their data files, kept unchanged for reference. They run from inside this folder:

```bash
cd legacy
pip install "pulp<4"   # the scripts use LpVariable.dicts with generators, which broke in PuLP 4.0
python 3.py
```

The maintained implementation lives in [`src/distnet`](../src/distnet) and reproduces the
same optimal profits (see the main README). The bundled instances in [`data/`](../data) were
generated from these files.
