from loader import *

def main():

    dfs = clean_data_eurobank()
    descriptions = get_descriptions(dfs)
    df_all = merge_dfs(dfs, "eurobank_all.csv")
    # separate_descriptions_in_batches(descriptions)
    # merge_batches()
    sanity_check(df_all)
    


if __name__ == "__main__":
    main()