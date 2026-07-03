# Iniital value replacement approach
```py
for k, v in mapping.items():
    if v in category_replacements.keys():
        mapping[k] = category_replacements.get(v)
```
# The if statement can be omitted by specifying a value to return if the specified key does not exist.

```py
for k, v in mapping.items():
    mapping[k] = category_replacements.get(v,v)
```
# List comprehesion for pythonic reasons

```py
mapping = {k: category_replacements.get(v, v) for k, v in mapping.items()}
```

---
# Generators and default dict
- Generators can only be iterated once
- It automatically assigns a default value to keys that do not exist

```py
PARQUETS = PARQUETS_PATH.glob("*.parquet") # This can be used only once
PARQUETS = list(PARQUETS_PATH.glob("*.parquet")) # Make it a list if you want to reuse it
```

```py
columns = dict()

for p in PARQUETS:
    df = pd.read_parquet(p)
    for c in sorted(df.columns):
        if c not in columns.keys():
            columns[c] = {df[c].dtype}
        
        else:
            columns[c].add(df[c].dtype)
``` 

```py
cs = defaultdict(set)

for p in PARQUETS:
    df = pd.read_parquet(p)
    for c in sorted(df.columns):
        cs[c].add(df[c].dtype)
```
