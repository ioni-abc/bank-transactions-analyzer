import json
import pandas as pd
from pathlib import Path


PROJECT_PATH = Path(__file__).parent.parent   # src/main.py → src/ → transactions/
DATA_PATH = PROJECT_PATH / "data"


def clean_data_eurobank():

    # load datasets
    eurobank_datasets = sorted(DATA_PATH.glob("eurobank_*.csv"))
    dfs = []

    for d in eurobank_datasets:
        
        df = pd.read_csv(d, skipfooter=4, engine="python", sep=";")
        #print(df.head(3))
        df = df.drop(["ΗΜ/ΝΙΑ ΑΞΙΑΣ", "Ονοματεπώνυμο/Επωνυμία Αντισυμβαλλόμενου"], axis=1)
        df = df.rename(columns = {
            "ΗΜ/ΝΙΑ ΚΙΝΗΣΗΣ": "date",
            "ΠΕΡΙΓΡΑΦΗ": "description",
            "ΠΟΣΟ": "amount",
            "ΥΠΟΛΟΙΠΟ": "balance",
        })
        df["date"] = pd.to_datetime(df["date"], dayfirst=True)
        
        for col in ["amount", "balance"]:
            df[col] = (
                df[col]
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
                .astype(float)
            )
        df["source"] = d.name

        print(f"--- {d.name}, rows: {len(df)}")
        print(f"NaNs: {df.isna().sum().to_dict()}")

        dfs.append(df)

    return dfs

def get_descriptions(dfs):
    
    descriptions = set()
    for df in dfs:
        descriptions.update(df["description"].dropna().unique())

    print(f"Num of descriptions: {len(descriptions)}")
    return descriptions

def merge_dfs(dfs, filename):

    df_all = pd.concat(dfs, ignore_index=True)
    df_all.to_csv(f"{DATA_PATH}/{filename}", index=False)

    print(df_all.dtypes)

    return df_all

def separate_descriptions_in_batches(all_descriptions):
    
    BATCH_SIZE = 200
    descriptions = sorted(all_descriptions)
    out_dir = PROJECT_PATH / "descriptions"
    out_dir.mkdir(exist_ok=True)

    for i in range(0, len(descriptions), BATCH_SIZE):

        batch = descriptions[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        out_file = out_dir / f"{batch_num:02d}.txt"
    
        with open(out_file, "w", encoding="utf-8") as f:
            for d in batch:
                f.write(d + "\n")
        
        print(f"Created {out_file.name} ({len(batch)} descriptions)")


def merge_batches():
    
    mappings_path = PROJECT_PATH / "mappings"
    batches = sorted(mappings_path.glob("batch_*.json"))
    batches_file = mappings_path / "eurobank_master_mapping.json"

    master = {}
    
    for b in batches:
        with open(b, "r", encoding="utf-8") as f:
            batch_data = json.load(f)
            master.update(batch_data)

    with open(batches_file, "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=4)
    
    print(f"Combined {len(batches)} batches into {len(master)} entries")


def sanity_check(df):
    
    eurobank_master_mapping_file = PROJECT_PATH / "mappings" / "eurobank_master_mapping.json"
    
    with open(eurobank_master_mapping_file, "r", encoding="utf-8") as f:
        master = json.load(f)

    all_descriptions = set(df["description"].dropna().unique())

    missing = all_descriptions - set(master.keys())
    extra = set(master.keys()) - all_descriptions

    print(f"In data but missing from master: {len(missing)}")
    print(f"In master but not in data: {len(extra)}")

    if missing:
        print("\n--- Missing descriptions ---")
        for d in sorted(missing):
            print(f"  {d!r}")


def find_misc_descriptions(df, mapping_file):

    master_mapping_file_path = PROJECT_PATH / "mappings" / mapping_file
    
    with open(master_mapping_file_path) as f:
        mappings = json.load(f)

    misc_descriptions = [k for k, v in mappings.items() if v == "misc"]

    with open(PROJECT_PATH / "mappings" / "misc_mappings.json", "w", encoding="utf-8") as f:
        json.dump(misc_descriptions, f, ensure_ascii=False, indent=4)

    non_misc_descr = {k: v for k, v in mappings.items() if v != "misc"}
    
    with open(PROJECT_PATH / "mappings" / "non_misc_mapping.json", "w", encoding="utf-8") as f:
        json.dump(non_misc_descr, f, ensure_ascii=False, indent=4)

    res = df[df["description"].isin(misc_descriptions)].sort_values("description")
    print(len(res))

    return res


def create_categories_eurobank(df):

    descriptions_to_categories_file = DATA_PATH / "mappings" / "wip.json"

    with open(descriptions_to_categories_file) as f:
        descriptions_to_categories = json.load(f)
    
    df["category"] = df["description"].map(descriptions_to_categories)

    return df


def create_parquet(df: pd.DataFrame, parquet_name: str):
    out_dir = DATA_PATH / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / parquet_name)


def revolut_to_revolut(df):
    entries = []
    r2r = df[
        (df["description"].str.contains("Revolut", case=False, na=False)) &
        (df["amount"] < 0)
        ].sort_values("date", ascending=False).reset_index()
    
    out_file = PROJECT_PATH / "mappings" / "rtr_mapping.txt"

    with open(out_file, "w", encoding="utf-8") as f:
        for i, row in r2r.iterrows():
            entries.append(
                {
                    "index": i,
                    "date": str(row["date"]),
                    "amount": row["amount"],
                    "new_description": ""
                }
            )
        json.dump(entries, f, ensure_ascii=False, indent=4)


def replace_revolut_bank_uab_descr(
        df: pd.DataFrame,
        filepath: Path
):
    # replacement_descr = dict()

    with open(filepath) as f:
        replacement_descr = json.load(f)
    
    for k, v in replacement_descr.items():
        print(f"{k}: {v}")
