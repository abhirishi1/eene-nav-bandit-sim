# Copyright 2023 Volvo Car Corporation
# Licensed under Apache 2.0.

import csv
import os

ROAD_GRAPH_COLUMNS = ['from_id', 'from_y', 'from_x', 'to_id', 'to_y', 'to_x', 'mean_consumption', 'mean_time']
CHARGING_STATION_COLUMNS = ['station_id', 'node_id', 'node_y', 'node_x', 'power']

MISSING_MARKER = '>>> MISSING <<<'


def find_csv_line_numbers(csv_path):
    """
    Find the line in the file where each data row starts, skipping blank lines the same way pd.read_csv does
    :param csv_path: Path to the CSV file
    :return: List with one line number (header line counted from 1) per data row, or None if the file can't be read
    """
    try:
        with open(csv_path, newline='', encoding='utf-8-sig') as csv_file:
            reader = csv.reader(csv_file)
            line_numbers = []
            previous_line_number = 0
            for row in reader:
                if row and not (len(row) == 1 and row[0].strip() == ''):
                    line_numbers.append(previous_line_number + 1)
                previous_line_number = reader.line_num
    except (OSError, UnicodeDecodeError, csv.Error):
        return None
    return line_numbers[1:]


def find_missing_data(df, required_columns, csv_path):
    """
    Describe missing required columns and blank required values in a CSV read with pandas
    :param df: DataFrame as returned by pd.read_csv(csv_path)
    :param required_columns: Names of the columns that must be present and filled in
    :param csv_path: Path of the CSV file, used for its name and line numbers in the messages
    :return: List of problem descriptions; each blank row is shown with its blank cells marked
    (cells holding only spaces count as blank)
    """
    file_name = os.path.basename(csv_path)
    problems = []
    for column in required_columns:
        if column not in df.columns:
            problems.append(file_name + ": required column '" + column + "' is missing "
                            "(columns found: " + ', '.join(str(c) for c in df.columns) + ")")
    present_columns = [column for column in required_columns if column in df.columns]
    blank_mask = df[present_columns].isna() | df[present_columns].apply(
        lambda values: values.map(lambda value: isinstance(value, str) and value.strip() == ''))
    if not blank_mask.to_numpy().any():
        return problems

    line_numbers = find_csv_line_numbers(csv_path)
    if line_numbers is not None and len(line_numbers) != len(df):
        line_numbers = None
    for row_position in range(len(df)):
        blank_row = blank_mask.iloc[row_position]
        blank_columns = [column for column in present_columns if blank_row[column]]
        if not blank_columns:
            continue
        row = df.iloc[row_position]
        highlighted_cells = [str(column) + '=' + (MISSING_MARKER if column in blank_columns else str(row[column]))
                             for column in df.columns]
        location = ('line ' + str(line_numbers[row_position]) if line_numbers is not None
                    else 'data row ' + str(row_position + 1))
        problems.append(file_name + ' ' + location + ': blank ' +
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
