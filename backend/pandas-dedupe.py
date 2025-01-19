import pandas as pd
import pandas_dedupe


if __name__ == '__main__':
    df = pd.read_csv('whitehouse-waves-2014_03.csv')
    print(df.head())

    df = pandas_dedupe.dedupe_dataframe(df, df.columns, update_model=False)
    df.to_excel('KNA2-deduped.xlsx', index=False)