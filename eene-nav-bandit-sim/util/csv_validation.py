# Copyright 2023 Volvo Car Corporation
# Licensed under Apache 2.0.

ROAD_GRAPH_COLUMNS = ['from_id', 'from_y', 'from_x', 'to_id', 'to_y', 'to_x', 'mean_consumption', 'mean_time']
CHARGING_STATION_COLUMNS = ['station_id', 'node_id', 'node_y', 'node_x', 'power']

MISSING_MARKER = '>>> MISSING <<<'


def find_missing_data(df, required_columns, file_name):
    """
    Describe missing required columns and blank required values in a CSV read with pandas
    :param df: DataFrame as returned by pd.read_csv
    :param required_columns: Names of the columns that must be present and filled in
    :param file_name: File name used in the messages
    :return: List of problem descriptions; each blank row is shown with its blank cells marked
    (line numbers count the header as line 1)
    """
    problems = []
    for column in required_columns:
        if column not in df.columns:
            problems.append(file_name + ": required column '" + column + "' is missing "
                            "(columns found: " + ', '.join(str(c) for c in df.columns) + ")")
    present_columns = [column for column in required_columns if column in df.columns]
    blank_mask = df[present_columns].isna()
    for row_position in range(len(df)):
        blank_row = blank_mask.iloc[row_position]
        blank_columns = [column for column in present_columns if blank_row[column]]
        if not blank_columns:
            continue
        row = df.iloc[row_position]
        highlighted_cells = [str(column) + '=' + (MISSING_MARKER if column in blank_columns else str(row[column]))
                             for column in df.columns]
        problems.append(file_name + ' line ' + str(row_position + 2) + ': blank ' +
                        ', '.join("'" + column + "'" for column in blank_columns) + '\n'
                        '      ' + ' | '.join(highlighted_cells))
    return problems


def stop_if_missing_data(problems):
    """
    Stop the program with a readable report if any input data is missing
    :param problems: Problem descriptions from find_missing_data
    """
    if problems:
        raise SystemExit('Missing data in input CSV files (' + str(len(problems)) + ' problem(s)); '
                         'nothing was processed. Fill in the gaps below and run again:\n  - ' +
                         '\n  - '.join(problems))
