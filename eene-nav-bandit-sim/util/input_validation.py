# Copyright 2023 Volvo Car Corporation
# Licensed under Apache 2.0.

import pandas as pd

ID_COLUMNS = ['from_id', 'to_id', 'station_id', 'node_id']

ROAD_GRAPH_REQUIRED_COLUMNS = ['from_id', 'from_y', 'from_x', 'to_id', 'to_y', 'to_x',
                               'mean_consumption', 'mean_time']
ROAD_GRAPH_NUMERIC_COLUMNS = ['mean_time', 'mean_consumption', 'from_y', 'from_x', 'to_y', 'to_x']

CHARGING_STATION_REQUIRED_COLUMNS = ['station_id', 'node_id', 'node_y', 'node_x', 'power']
CHARGING_STATION_NUMERIC_COLUMNS = ['power', 'node_y', 'node_x']


def read_csv_with_string_ids(csv_path):
    """Read a CSV keeping ID columns as strings (e.g. '007' stays '007') and stripping header whitespace."""
    header = pd.read_csv(csv_path, nrows=0).columns
    id_dtypes = {column: str for column in header if column.strip() in ID_COLUMNS}
    df = pd.read_csv(csv_path, dtype=id_dtypes)
    df.columns = df.columns.str.strip()
    return df


def validate_columns(df, required, name='DataFrame'):
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(name + ' is missing required column(s): ' + ', '.join(missing) +
                         '. Found columns: ' + ', '.join(str(column) for column in df.columns))


def coerce_numeric(df, cols, name='DataFrame'):
    """Convert columns to numbers in place; raise listing every value that is blank or not a number."""
    problems = []
    for column in cols:
        original = df[column]
        converted = pd.to_numeric(original, errors='coerce')
        for row_index in converted.index[converted.isna()]:
            value = original.loc[row_index]
            shown = '<blank>' if pd.isna(value) else repr(value)
            problems.append('row ' + str(row_index) + ' ' + column + '=' + shown)
        df[column] = converted
    if problems:
        raise ValueError(name + ' has non-numeric values: ' + '; '.join(problems))
    return df
