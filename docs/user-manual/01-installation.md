
# Installation

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .[dev,auth]     # add [secrets],[keyvault],[docs] as needed
pre-commit install
```
