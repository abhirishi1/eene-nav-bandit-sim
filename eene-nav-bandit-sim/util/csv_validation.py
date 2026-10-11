# Copyright 2023 Volvo Car Corporation
# Licensed under Apache 2.0.

import numpy as np

ROAD_GRAPH_COLUMNS = ['from_id', 'from_y', 'from_x', 'to_id', 'to_y', 'to_x', 'mean_consumption', 'mean_time']
CHARGING_STATION_COLUMNS = ['station_id', 'node_id', 'node_y', 'node_x', 'power']


def find_column_problems(df, required_columns, file_name):
    """
    List missing required columns and blank values in a CSV read with pandas
    :param df: DataFrame as returned by pd.read_csv
    :param required_columns: Names of the columns that must be present and filled in
    :param file_name: File name used in the messages
    :return: List of problem messages (line numbers count the header as line 1)
    """
    problems = []
    for column in required_columns:
        if column not in df.columns:
            problems.append(file_name + " is missing required column '" + column + "'")
            continue
        for row_position in np.flatnonzero(df[column].isna().to_numpy()):
            problems.append(file_name + ' line ' + str(row_position + 2) + ": column '" + column + "' is blank")
    return problems


def raise_if_problems(problems):
    if problems:
        raise ValueError('Invalid input CSV:\n  - ' + '\n  - '.join(problems))


def check_required_columns(df, required_columns, file_name):
    raise_if_problems(find_column_problems(df, required_columns, file_name))
