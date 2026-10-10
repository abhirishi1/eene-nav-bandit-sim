# Copyright 2023 Volvo Car Corporation
# Licensed under Apache 2.0.

import numpy as np
import pandas as pd

ROAD_GRAPH_COLUMNS = ['from_id', 'from_y', 'from_x', 'to_id', 'to_y', 'to_x', 'mean_consumption', 'mean_time']
CHARGING_STATION_COLUMNS = ['station_id', 'node_id', 'node_y', 'node_x', 'power']
MAX_REPORTED_ERRORS = 20


def validate_road_graph_df(road_graph_df, source_name='road graph CSV'):
    """ Return a list of human-readable problems found in the road graph DataFrame (empty if valid). """
    errors = _missing_column_errors(road_graph_df, ROAD_GRAPH_COLUMNS, source_name)
    if errors:
        return errors
    errors += _blank_value_errors(road_graph_df, ['from_id', 'to_id'], source_name)
    errors += _numeric_value_errors(road_graph_df, 'mean_consumption', source_name)
    errors += _numeric_value_errors(road_graph_df, 'mean_time', source_name, must_be_positive=True)
    return errors


def validate_charging_station_df(charging_station_df, source_name='charging station CSV', road_graph_df=None):
    """ Return a list of human-readable problems found in the charging station DataFrame (empty if valid).
    If road_graph_df is given, every station node_id must also appear in the road graph. """
    errors = _missing_column_errors(charging_station_df, CHARGING_STATION_COLUMNS, source_name)
    if errors:
        return errors
    errors += _blank_value_errors(charging_station_df, ['station_id', 'node_id'], source_name)
    errors += _numeric_value_errors(charging_station_df, 'power', source_name, must_be_positive=True)

    station_ids = charging_station_df['station_id']
    duplicated = station_ids.duplicated(keep='first') & ~_is_blank(station_ids)
    for index in charging_station_df.index[duplicated]:
        errors.append(_row_message(source_name, index,
                                   "station_id '{}' is used more than once".format(station_ids[index])))

    if road_graph_df is not None and not _missing_column_errors(road_graph_df, ['from_id', 'to_id'], ''):
        road_node_ids = set(road_graph_df['from_id'].astype(str)) | set(road_graph_df['to_id'].astype(str))
        node_ids = charging_station_df['node_id']
        for index in charging_station_df.index[~_is_blank(node_ids)]:
            if str(node_ids[index]) not in road_node_ids:
                errors.append(_row_message(source_name, index,
                                           "node_id '{}' does not appear in the road graph".format(node_ids[index])))
    return errors


def validate_trip_end_points(charging_station_df, start_node_id, end_node_id, source_name='charging station CSV'):
    """ Return a list of problems with the start and end node IDs (each must be a charging station node_id). """
    if 'node_id' not in charging_station_df.columns:
        return []
    station_node_ids = set(charging_station_df['node_id'].astype(str))
    errors = []
    for setting_name, node_id in [('--start-node-id', start_node_id), ('--end-node-id', end_node_id)]:
        if node_id is None:
            errors.append('{} is required'.format(setting_name))
        elif str(node_id) not in station_node_ids:
            errors.append("{} '{}' is not the node_id of any station in {}".format(setting_name, node_id, source_name))
    return errors


def format_validation_errors(errors):
    """ Format a list of problems as one message, listing at most MAX_REPORTED_ERRORS of them. """
    lines = ['Input data validation failed with {} problem(s):'.format(len(errors))]
    lines += ['  - ' + error for error in errors[:MAX_REPORTED_ERRORS]]
    if len(errors) > MAX_REPORTED_ERRORS:
        lines.append('  ... and {} more'.format(len(errors) - MAX_REPORTED_ERRORS))
    return '\n'.join(lines)


def _missing_column_errors(df, required_columns, source_name):
    missing_columns = [column for column in required_columns if column not in df.columns]
    if not missing_columns:
        return []
    return ['{}: missing required column(s): {}'.format(source_name, ', '.join(missing_columns))]


def _blank_value_errors(df, columns, source_name):
    errors = []
    for column in columns:
        for index in df.index[_is_blank(df[column])]:
            errors.append(_row_message(source_name, index, '{} is blank'.format(column)))
    return errors


def _numeric_value_errors(df, column, source_name, must_be_positive=False):
    errors = []
    blank = _is_blank(df[column])
    numbers = pd.to_numeric(df[column], errors='coerce')
    for index in df.index:
        if blank[index]:
            errors.append(_row_message(source_name, index, '{} is blank'.format(column)))
        elif not np.isfinite(numbers[index]):
            errors.append(_row_message(source_name, index,
                                       "{} '{}' is not a valid number".format(column, df[column][index])))
        elif must_be_positive and numbers[index] <= 0:
            errors.append(_row_message(source_name, index,
                                       '{} must be greater than 0 (found {})'.format(column, df[column][index])))
    return errors


def _is_blank(series):
    return series.isna() | (series.astype(str).str.strip() == '')


def _row_message(source_name, index, problem):
    # Line numbers count the header as line 1, so the first data row is line 2.
    return '{} line {}: {}'.format(source_name, index + 2, problem)
