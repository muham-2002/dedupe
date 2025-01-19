# Chala hua code
import math
import dedupe.variables
import dedupe.variables.string
import pandas as pd
import dedupe
from unidecode import unidecode
import re
import os
import json
import logging
from typing import Dict, List, Any, Tuple
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def preprocess(column):
    """Clean data using Unidecode and Regex"""
    if not column:
        return None

    column = unidecode(str(column))
    column = re.sub('  +', ' ', column)
    column = re.sub('\n', ' ', column)
    column = column.strip().strip('"').strip("'").lower().strip()
    return None if not column else column


def convert_df_to_dedupe_format(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Convert DataFrame to dictionary format required by dedupe"""
    data_d = {}
    for idx, row in df.iterrows():
        clean_row = {}
        for column, value in row.items():
            if column != 'source_file':  # Skip metadata columns
                clean_row[column] = preprocess(value)
        data_d[str(idx)] = clean_row
    return data_d


def get_training_pairs(data_d: Dict[str, Dict[str, Any]], config: Dict) -> Dict[str, List[Dict[str, Dict[str, Any]]]]:
    """
    Generate training pairs from the data using exact matches for training
    """
    training_pairs = {
        'match': [],
        'distinct': []
    }

    records = list(data_d.items())
    matches_found = 0
    distinct_found = 0

    # Get fields for matching
    # Default to email and phone
    match_fields = config.get('match_fields', ['email', 'phone'])

    # Create an index for exact matches
    exact_matches = {}
    for record_id, record in records:
        # Create a composite key from match fields
        key_parts = []
        for field in match_fields:
            if field in record and record[field]:
                key_parts.append(str(record[field]).lower().strip())

        if key_parts:  # Only if we have values for match fields
            key = '|'.join(key_parts)
            if key not in exact_matches:
                exact_matches[key] = []
            exact_matches[key].append((record_id, record))

    # Find exact matches
    for key, matching_records in exact_matches.items():
        if len(matching_records) > 1:  # We found duplicates
            # Take pairs of records that match exactly
            for i, (record1_id, record1) in enumerate(matching_records):
                for record2_id, record2 in matching_records[i+1:]:
                    if matches_found >= config.get('max_training_matches', 5):
                        break

                    training_pairs['match'].append({
                        '0': record1,
                        '1': record2
                    })
                    matches_found += 1

                if matches_found >= config.get('max_training_matches', 5):
                    break

    # Find distinct pairs (records that don't match on any field)
    processed_pairs = set()
    for i, (record1_id, record1) in enumerate(records):
        if distinct_found >= config.get('max_training_distincts', 5):
            break

        for record2_id, record2 in records[i+1:]:
            if distinct_found >= config.get('max_training_distincts', 5):
                break

            # Skip if we've seen this pair
            pair_key = tuple(sorted([record1_id, record2_id]))
            if pair_key in processed_pairs:
                continue

            processed_pairs.add(pair_key)

            # Check if they're different on all match fields
            is_distinct = True
            for field in match_fields:
                val1 = str(record1.get(field, '')).lower().strip()
                val2 = str(record2.get(field, '')).lower().strip()
                if val1 and val2 and val1 == val2:
                    is_distinct = False
                    break

            if is_distinct:
                training_pairs['distinct'].append({
                    '0': record1,
                    '1': record2
                })
                distinct_found += 1

    logger.info(
        f"Generated {len(training_pairs['match'])} matching pairs and {len(training_pairs['distinct'])} distinct pairs")
    return training_pairs


def read_excel_file(file_path: str, chunk_size: int) -> pd.DataFrame:
    """
    Read Excel file in chunks to handle large files

    Args:
        file_path: Path to the Excel file
        chunk_size: Number of rows to read at a time

    Returns:
        DataFrame containing all data from the Excel file
    """
    logger.info(f"Reading Excel file: {file_path}")

    # First read to get headers
    df_info = pd.read_excel(file_path, nrows=0)
    headers = df_info.columns.tolist()

    # Get total rows using openpyxl
    wb = pd.ExcelFile(file_path).book
    sheet = wb.active
    total_rows = sheet.max_row

    # Initialize empty DataFrame
    data = pd.DataFrame()

    # Read in chunks
    for start_row in range(0, total_rows, chunk_size):
        end_row = min(start_row + chunk_size, total_rows)
        chunk = pd.read_excel(
            file_path,
            skiprows=range(1, start_row + 1) if start_row > 0 else None,
            nrows=chunk_size if start_row == 0 else end_row - start_row
        )

        if start_row > 0:  # Add headers for chunks after first
            chunk.columns = headers

        chunk['source_file'] = os.path.basename(file_path)
        data = pd.concat([data, chunk], ignore_index=True)
        logger.info(f"Read rows {start_row} to {end_row} of {total_rows}")

    return data


def read_csv_file(file_path: str, chunk_size: int) -> pd.DataFrame:
    """
    Read CSV file in chunks to handle large files

    Args:
        file_path: Path to the CSV file
        chunk_size: Number of rows to read at a time

    Returns:
        DataFrame containing all data from the CSV file
    """
    logger.info(f"Reading CSV file: {file_path}")

    data = pd.DataFrame()
    csv_chunks = pd.read_csv(file_path, chunksize=chunk_size, encoding='utf-8')

    for chunk in csv_chunks:
        chunk['source_file'] = os.path.basename(file_path)
        data = pd.concat([data, chunk], ignore_index=True)

    return data


def read_input_files(file_paths: List[str], chunk_size: int) -> pd.DataFrame:
    """
    Read multiple input files and combine them into a single DataFrame

    Args:
        file_paths: List of file paths to read
        chunk_size: Number of rows to read at a time

    Returns:
        Combined DataFrame from all input files
    """
    all_data = pd.DataFrame()

    for file_path in file_paths:
        try:
            if file_path.endswith(('.xlsx', '.xls')):
                df = read_excel_file(file_path, chunk_size)
            else:
                df = read_csv_file(file_path, chunk_size)

            all_data = pd.concat([all_data, df], ignore_index=True)

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)}")
            raise

    logger.info(f"Total records loaded: {len(all_data)}")
    return all_data


def detect_fields(file_path: str) -> List[Dict]:
    """
    Detect fields from the first file and create field configurations.
    Returns only first 2 fields as match fields.

    Args:
        file_path: Path to the file to detect fields from

    Returns:
        Tuple of (field configurations, match fields)
    """
    try:
        # Read first row to get column names
        if file_path.endswith(('.xlsx', '.xls')):
            df_sample = pd.read_excel(file_path, nrows=1)
        else:
            df_sample = pd.read_csv(file_path, nrows=1, encoding='utf-8')

        # Get all columns except source_file as fields
        columns = [col for col in df_sample.columns if col != 'source_file']

        # Create field configurations
        fields = [
            {'field': col, 'type': 'String', 'has_missing': True}
            for col in columns
        ]

        # Use only first 2 columns as match fields
        match_fields = columns[:2]
        logger.info(f"Using first 2 fields as match fields: {match_fields}")

        return fields, match_fields

    except Exception as e:
        logger.error(f"Error detecting fields from file {file_path}: {str(e)}")
        raise


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize data"""
    # Convert all columns to string and lowercase
    for col in df.columns:
        if col != 'source_file':  # Skip metadata columns
            df[col] = df[col].astype(str).str.lower()
            # Clean punctuation but preserve useful characters
            df[col] = df[col].str.replace('[^\w\s\.\-\(\)\,\:\/\\\\]', '')
            # Handle null values
            df[col] = df[col].replace({'nan': None, 'none': None, 'nat': None})
            # Apply unidecode and trim
            df[col] = df[col].apply(
                lambda x: preprocess(x) if x is not None else None)
    return df


def prepare_training_data(config: Dict, deduper: dedupe.Dedupe, data_d: Dict) -> Dict:
    """Prepare training data with better sampling"""
    
    uncertain_pairs = []
    max_pairs = config.get('max_training_pairs', 40)
    
    # Get uncertain pairs from dedupe using sampled data
    try:
        while len(uncertain_pairs) < max_pairs:
            pair = deduper.uncertain_pairs()
            if not pair:
                break
                
            # Add field metadata to help frontend display
            pair_data = {
                '0': pair[0][0],
                '1': pair[0][1],
            }
            
            uncertain_pairs.append(pair_data)
            
    except IndexError:
        pass
        
    logger.info(f"Found {len(uncertain_pairs)} uncertain pairs")
    
    return {
        'pairs': uncertain_pairs,
        'status': 'needs_training',
        'data_d': data_d  # Return the data dictionary with the response
    }


def process_training_results(training_data: List[Dict], deduper: dedupe.Dedupe, data_d: Dict) -> Tuple[dedupe.Dedupe, Dict]:
    """Process labeled pairs and train model"""
    formatted_pairs = {
        'match': [],
        'distinct': []
    }
    
    stats = {
        'matches_processed': 0,
        'distincts_processed': 0,
        'uncertain_skipped': 0,
        'exact_matches_used': 0
    }
    
    for pair in training_data:
        # Get the records from the full dataset
        record_1 = data_d.get(pair['0']['record_id']) if isinstance(pair['0'], dict) and 'record_id' in pair['0'] else pair['0']
        record_2 = data_d.get(pair['1']['record_id']) if isinstance(pair['1'], dict) and 'record_id' in pair['1'] else pair['1']
        
        if pair['answer'] == 'y':
            formatted_pairs['match'].append((record_1, record_2))
            stats['matches_processed'] += 1
            if pair.get('exact_match_fields'):
                stats['exact_matches_used'] += 1
        elif pair['answer'] == 'n':
            formatted_pairs['distinct'].append((record_1, record_2))
            stats['distincts_processed'] += 1
        else:
            stats['uncertain_skipped'] += 1
    
    # Train model
    logger.info(f"Training model with {len(formatted_pairs['match'])} match pairs and {len(formatted_pairs['distinct'])} distinct pairs")
    deduper.mark_pairs(formatted_pairs)
    logger.info("Training model...")
    deduper.train()
    
    return deduper, stats


def find_duplicates_in_files(
    training_data,
    file_paths: List[str],
    output_file: str = None,
    settings_file: str = 'learned_settings',
    config: Dict = None,
    sample_size_float: float = 0.2
) -> List[Dict]:

    # Detect fields if not specified
    if not config['fields']:
        config['fields'], config['match_fields'] = detect_fields(file_paths[0])

    # Read all input files
    all_data = read_input_files(file_paths, config['chunk_size'])

    # Validate data is not empty
    if len(all_data) == 0:
        raise ValueError("No data found in input files")

    # Print data summary
    logger.info("Data Summary:")
    for file_path in file_paths:
        file_data = all_data[all_data['source_file']
                             == os.path.basename(file_path)]
        logger.info(f"- {file_path}: {len(file_data)} records")

    # Clean data
    all_data = clean_data(all_data)

    # Convert data to dedupe format
    data_d = convert_df_to_dedupe_format(all_data)

    # Convert field configurations to dedupe format
    variable_definition = []
    for field_config in config['fields']:
        field_type = field_config['type']
        field_name = field_config['field']
        has_missing = field_config.get('has_missing', False)
        
        # Create the appropriate dedupe variable based on type
        if field_type == 'String':
            field_def = dedupe.variables.String(
                field_name,
                has_missing=has_missing
            )
        elif field_type == 'Text':
            field_def = dedupe.variables.Text(
                field_name,
                has_missing=has_missing
            )
        elif field_type == 'Price':
            field_def = dedupe.variables.Price(
                field_name,
                has_missing=has_missing
            )
        elif field_type == 'DateTime':
            field_def = dedupe.variables.DateTime(
                field_name,
                has_missing=has_missing
            )
        else:
            # Default to String type if unknown
            field_def = dedupe.variables.String(
                field_name,
                has_missing=has_missing
            )
        
        variable_definition.append(field_def)


    # Initialize deduper with variable definition
    logger.info(f"Initializing deduper with {len(variable_definition)} fields")
    deduper = dedupe.Dedupe(variable_definition, num_cores=4)

    # Calculate sample size
    total_records = len(data_d)
    target_sample_size = math.floor(total_records * sample_size_float)
    max_sample_size = 1500
    sample_size = min(target_sample_size, max_sample_size)

    # If total records are less than sample size, use all records
    if total_records <= sample_size:
        logger.info(f"Total records ({total_records}) less than or equal to sample size. Using all records for training.")
        training_data_d = data_d
    else:
        # Create a smaller dataset for training preparation
        all_record_ids = list(data_d.keys())
        sampled_record_ids = random.sample(all_record_ids, sample_size)
        training_data_d = {rid: data_d[rid] for rid in sampled_record_ids}
        logger.info(f"Using sampled data of {len(training_data_d)} records from total {total_records} records")

    # Prepare training with sampled data
    deduper.prepare_training(training_data_d)

    if training_data is None:
        # Get training pairs using truncated data
        return prepare_training_data(config, deduper, data_d)
    else:
        # Process training results using full dataset
        deduper, stats = process_training_results(training_data, deduper, data_d)

        # Find duplicates using full dataset
        threshold = config['similarity_threshold']
        logger.info(f"Using threshold: {threshold}")
        clustered_dupes = deduper.partition(data_d, threshold)

        # Format results
        results = []
        cluster_membership = {}

        for cluster_id, (records, scores) in enumerate(clustered_dupes):
            # Save cluster membership for each record
            for record_id, score in zip(records, scores):
                cluster_membership[record_id] = {
                    "cluster_id": cluster_id,
                    "confidence_score": score
                }

            if len(records) > 1:  # Only include actual duplicates
                cluster_records = []
                for record_id, score in zip(records, scores):
                    record = data_d[record_id].copy()
                    record.update({
                        'confidence_score': score,
                        'source_file': all_data.loc[int(record_id), 'source_file'],
                        'record_id': record_id
                    })
                    cluster_records.append(record)

                # Only add clusters where records are from different files or have exact matches
                has_duplicates = False
                for i, rec1 in enumerate(cluster_records):
                    for rec2 in cluster_records[i+1:]:
                        # Check if records are from different files
                        if rec1['source_file'] != rec2['source_file']:
                            has_duplicates = True
                            break

                        # Check for exact matches on any match field
                        for field in config['match_fields']:
                            if (field in rec1 and field in rec2 and
                                rec1[field] and rec2[field] and
                                    rec1[field] == rec2[field]):
                                has_duplicates = True
                                break

                        if has_duplicates:
                            break

                    if has_duplicates:
                        break

                if has_duplicates:
                    results.append({
                        'cluster_id': cluster_id,
                        'group_size': len(cluster_records),
                        'confidence_score': sum(r['confidence_score'] for r in cluster_records) / len(cluster_records),
                        'records': cluster_records
                    })

        results = sorted(
            results, key=lambda x: x['confidence_score'], reverse=True)

        # Save results if output file is specified
        if output_file:
            # Convert numpy float32 values to native Python floats for JSON serialization
            json_results = []
            for result in results:
                result_copy = result.copy()
                result_copy['confidence_score'] = float(
                    result_copy['confidence_score'])
                records = []
                for record in result_copy['records']:
                    record_copy = record.copy()
                    record_copy['confidence_score'] = float(
                        record_copy['confidence_score'])
                    records.append(record_copy)
                result_copy['records'] = records
                json_results.append(result_copy)

            # Include training statistics in results
            results_data = {
                'total_records': len(all_data),
                'duplicate_groups_found': len(results),
                'duplicates': json_results,
                'configuration': config,
                'threshold_used': float(threshold),
                'training_stats': stats
            }
            with open(output_file, 'w') as f:
                json.dump(results_data, f, indent=2)
            logger.info(f"Results saved to {output_file}")

        return results


if __name__ == "__main__":

    # input_files = ['KNA1.xlsx']  # Your input file
    input_files = ['whitehouse-waves-2014_03.csv']

    # Optimized configuration for better duplicate detection
    config = {
        'similarity_threshold': 0.0,
        'required_matches': 1,
        'chunk_size': 50000,
        'max_training_matches': 5,
        'max_training_distincts': 5,
        'max_training_pairs': 100,
        'recall_weight': 1.0,
        'fields': []
    }

    # Use the find_duplicates_in_files function

    data = {
        "pairs": [{'0': {'NAMELAST': 'nance', 'NAMEFIRST': 'valerie', 'NAMEMID': 'a', 'UIN': 'u58463', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '2/26/2014 0:00', 'APPT_START_DATE': '3/12/2014 9:00', 'APPT_END_DATE': '3/12/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '299.0', 'LAST_UPDATEDBY': 'am', 'POST': 'win', 'LASTENTRYDATE': '2/26/2014 10:16', 'TERMINAL_SUFFIX': 'am', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'browne', 'NAMEFIRST': 'matthew', 'NAMEMID': 'j', 'UIN': 'u57436', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/7/2014 0:00', 'APPT_START_DATE': '3/11/2014 9:30', 'APPT_END_DATE': '3/11/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '185.0', 'LAST_UPDATEDBY': 'mb', 'POST': 'win', 'LASTENTRYDATE': '3/7/2014 19:04', 'TERMINAL_SUFFIX': 'mb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'krupp', 'NAMEFIRST': 'gloria', 'NAMEMID': None, 'UIN': 'u65310', 'BDGNBR': '0.0', 'ACCESS_TYPE': 'va', 'TOA': '3/21/2014 7:55', 'POA': 'vis01', 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/21/2014 0:00', 'APPT_START_DATE': '3/21/2014 7:53', 'APPT_END_DATE': '3/21/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '2.0', 'LAST_UPDATEDBY': 'mb', 'POST': 'win', 'LASTENTRYDATE': '3/21/2014 7:53', 'TERMINAL_SUFFIX': 'mb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'schwoyer', 'NAMEFIRST': 'arlan', 'NAMEMID': 'r', 'UIN': 'u44415', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '12/26/2013 0:00', 'APPT_START_DATE': '1/3/2014 11:00', 'APPT_END_DATE': '1/3/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '260.0', 'LAST_UPDATEDBY': 'jc', 'POST': 'win', 'LASTENTRYDATE': '12/26/2013 13:04', 'TERMINAL_SUFFIX': 'jc', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'f', 'RELEASE_DATE': '4/25/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'willi', 'NAMEFIRST': 'cosima', 'NAMEMID': 'c', 'UIN': 'u51535', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41680', 'APPT_START_DATE': '41681.3125', 'APPT_END_DATE': '41681.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '5707.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '41680.67579', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': None, 'visitee_namefirst': 'potus', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'south lawn', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, '1': {'NAMELAST': 'peters', 'NAMEFIRST': 'joanne', 'NAMEMID': 'e', 'UIN': 'u51535', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41680', 'APPT_START_DATE': '41681.3125', 'APPT_END_DATE': '41681.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '5707.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '41680.66962', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': None, 'visitee_namefirst': 'potus', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'south lawn', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'knight', 'NAMEFIRST': 'douglas', 'NAMEMID': 'k', 'UIN': 'u51535', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41680', 'APPT_START_DATE': '41681.3125', 'APPT_END_DATE': '41681.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '5707.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '41680.6648', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': None, 'visitee_namefirst': 'potus', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'south lawn', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, '1': {'NAMELAST': 'william', 'NAMEFIRST': 'blount', 'NAMEMID': 'w', 'UIN': 'u51535', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41680', 'APPT_START_DATE': '41681.3125', 'APPT_END_DATE': '41681.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '5707.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '41680.6758', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': None, 'visitee_namefirst': 'potus', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'south lawn', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'valentine', 'NAMEFIRST': 'loretta', 'NAMEMID': 'd', 'UIN': 'u63852', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/17/2014 0:00', 'APPT_START_DATE': '3/25/2014 11:30', 'APPT_END_DATE': '3/25/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '281.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '3/17/2014 7:23', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'littleford', 'NAMEFIRST': 'brooke', 'NAMEMID': 'a', 'UIN': 'u45010', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '1/8/2014 0:00', 'APPT_START_DATE': '1/10/2014 9:30', 'APPT_END_DATE': '1/10/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '88.0', 'LAST_UPDATEDBY': 'mb', 'POST': 'win', 'LASTENTRYDATE': '1/8/2014 12:09', 'TERMINAL_SUFFIX': 'mb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '4/25/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'astepho', 'NAMEFIRST': 'abdulahed', 'NAMEMID': None, 'UIN': 'u64127', 'BDGNBR': '92647.0', 'ACCESS_TYPE': 'va', 'TOA': '3/18/2014 15:54', 'POA': 'd1102', 'TOD': '3/18/2014 17:15', 'POD': None, 'APPT_MADE_DATE': '3/18/2014 0:00', 'APPT_START_DATE': '3/18/2014 16:00', 'APPT_END_DATE': '3/18/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '5.0', 'LAST_UPDATEDBY': 'ah', 'POST': 'win', 'LASTENTRYDATE': '3/18/2014 14:10', 'TERMINAL_SUFFIX': 'ah', 'visitee_namelast': 'philip', 'visitee_namefirst': 'dr.', 'MEETING_LOC': 'oeob', 'MEETING_ROOM': '326', 'CALLER_NAME_LAST': 'hanson', 'CALLER_NAME_FIRST': 'anissa', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'smith', 'NAMEFIRST': 'stuart', 'NAMEMID': 'n', 'UIN': 'u60393', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/13/2014 0:00', 'APPT_START_DATE': '3/14/2014 16:00', 'APPT_END_DATE': '3/14/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '534.0', 'LAST_UPDATEDBY': 'cm', 'POST': 'win', 'LASTENTRYDATE': '3/13/2014 18:04', 'TERMINAL_SUFFIX': 'cm', 'visitee_namelast': None, 'visitee_namefirst': 'potus/flotus', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'state floo', 'CALLER_NAME_LAST': 'mcnamaralawder', 'CALLER_NAME_FIRST': 'claudia', 'CALLER_ROOM': None, 'description': 'the event is on the state floor.', 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'kisida', 'NAMEFIRST': 'brian', 'NAMEMID': None, 'UIN': 'u55321', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41684', 'APPT_START_DATE': '41685.33333', 'APPT_END_DATE': '41685.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '169.0', 'LAST_UPDATEDBY': 'mb', 'POST': 'win', 'LASTENTRYDATE': '41684.41022', 'TERMINAL_SUFFIX': 'mb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '5/30/2014'}, '1': {'NAMELAST': 'kern', 'NAMEFIRST': 'john', 'NAMEMID': 'w', 'UIN': 'u52033', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41671', 'APPT_START_DATE': '41685.35417', 'APPT_END_DATE': '41685.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '285.0', 'LAST_UPDATEDBY': 'lj', 'POST': 'win', 'LASTENTRYDATE': '41671.49787', 'TERMINAL_SUFFIX': 'lj', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'schreiner', 'NAMEFIRST': 'sophia', 'NAMEMID': 'b', 'UIN': 'u63867', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/17/2014 0:00', 'APPT_START_DATE': '3/25/2014 12:00', 'APPT_END_DATE': '3/25/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '282.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '3/17/2014 7:38', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'steeves', 'NAMEFIRST': 'james', 'NAMEMID': 'n', 'UIN': 'u57149', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '2/21/2014 0:00', 'APPT_START_DATE': '3/1/2014 9:30', 'APPT_END_DATE': '3/1/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '155.0', 'LAST_UPDATEDBY': 'am', 'POST': 'win', 'LASTENTRYDATE': '2/21/2014 12:49', 'TERMINAL_SUFFIX': 'am', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'marti', 'NAMEFIRST': 'bryan', 'NAMEMID': 'f', 'UIN': 'u62026', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/11/2014 0:00', 'APPT_START_DATE': '3/13/2014 10:00', 'APPT_END_DATE': '3/13/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '161.0', 'LAST_UPDATEDBY': 'lj', 'POST': 'win', 'LASTENTRYDATE': '3/11/2014 8:57', 'TERMINAL_SUFFIX': 'lj', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'emhardt', 'NAMEFIRST': 'william', 'NAMEMID': 'f', 'UIN': 'u64666', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/19/2014 0:00', 'APPT_START_DATE': '3/21/2014 8:00', 'APPT_END_DATE': '3/21/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '261.0', 'LAST_UPDATEDBY': 'am', 'POST': 'win', 'LASTENTRYDATE': '3/19/2014 11:33', 'TERMINAL_SUFFIX': 'am', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'franchina', 'NAMEFIRST': 'annalise', 'NAMEMID': 'e', 'UIN': 'u45361', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '1/4/2014 0:00', 'APPT_START_DATE': '1/16/2014 8:30', 'APPT_END_DATE': '1/16/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '120.0', 'LAST_UPDATEDBY': 'mb', 'POST': 'win', 'LASTENTRYDATE': '1/4/2014 11:01', 'TERMINAL_SUFFIX': 'mb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '4/25/2014'}, '1': {'NAMELAST': 'shegota', 'NAMEFIRST': 'jodi', 'NAMEMID': 'a', 'UIN': 'u62339', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/11/2014 0:00', 'APPT_START_DATE': '3/21/2014 11:30', 'APPT_END_DATE': '3/21/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '275.0', 'LAST_UPDATEDBY': 'mb', 'POST': 'win', 'LASTENTRYDATE': '3/11/2014 16:04', 'TERMINAL_SUFFIX': 'mb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'burgos', 'NAMEFIRST': 'willy', 'NAMEMID': None, 'UIN': 'u44426', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '12/28/2013 0:00', 'APPT_START_DATE': '1/3/2014 11:30', 'APPT_END_DATE': '1/3/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '271.0', 'LAST_UPDATEDBY': 'jc', 'POST': 'win', 'LASTENTRYDATE': '12/28/2013 10:35', 'TERMINAL_SUFFIX': 'jc', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '4/25/2014'}, '1': {'NAMELAST': 'jin', 'NAMEFIRST': 'sejung', 'NAMEMID': None, 'UIN': 'u55707', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41687', 'APPT_START_DATE': '41698.3125', 'APPT_END_DATE': '41698.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '275.0', 'LAST_UPDATEDBY': 'jc', 'POST': 'win', 'LASTENTRYDATE': '41687.4502', 'TERMINAL_SUFFIX': 'jc', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '5/30/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'livesay', 'NAMEFIRST': 'kimberly', 'NAMEMID': 'b', 'UIN': 'u58729', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41696', 'APPT_START_DATE': '41698.41667', 'APPT_END_DATE': '41698.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '145.0', 'LAST_UPDATEDBY': 'mb', 'POST': 'win', 'LASTENTRYDATE': '41696.75253', 'TERMINAL_SUFFIX': 'mb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '5/30/2014'}, '1': {'NAMELAST': 'brooks', 'NAMEFIRST': 'chloe', 'NAMEMID': 'n', 'UIN': 'u62327', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/11/2014 0:00', 'APPT_START_DATE': '3/21/2014 10:30', 'APPT_END_DATE': '3/21/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '275.0', 'LAST_UPDATEDBY': 'mb', 'POST': 'win', 'LASTENTRYDATE': '3/11/2014 15:05', 'TERMINAL_SUFFIX': 'mb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'park', 'NAMEFIRST': 'emily', 'NAMEMID': 'e', 'UIN': 'u51535', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41680', 'APPT_START_DATE': '41681.3125', 'APPT_END_DATE': '41681.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '5707.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '41680.66926', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': None, 'visitee_namefirst': 'potus', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'south lawn', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, '1': {'NAMELAST': 'mcgrath', 'NAMEFIRST': 'catherine', 'NAMEMID': 'e', 'UIN': 'u51535', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41680', 'APPT_START_DATE': '41681.3125', 'APPT_END_DATE': '41681.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '5707.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '41680.667', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': None, 'visitee_namefirst': 'potus', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'south lawn', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'miele', 'NAMEFIRST': 'sara', 'NAMEMID': None, 'UIN': 'u45012', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '1/2/2014 0:00', 'APPT_START_DATE': '1/10/2014 8:30', 'APPT_END_DATE': '1/10/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '142.0', 'LAST_UPDATEDBY': 'mb', 'POST': 'win', 'LASTENTRYDATE': '1/2/2014 16:22', 'TERMINAL_SUFFIX': 'mb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '4/25/2014'}, '1': {'NAMELAST': 'chie', 'NAMEFIRST': 'brandon', 'NAMEMID': 'j', 'UIN': 'u63889', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/17/2014 0:00', 'APPT_START_DATE': '3/25/2014 12:30', 'APPT_END_DATE': '3/25/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '283.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '3/17/2014 11:28', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'snow', 'NAMEFIRST': 'bobbi', 'NAMEMID': 'j', 'UIN': 'u63499', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/15/2014 0:00', 'APPT_START_DATE': '3/27/2014 9:00', 'APPT_END_DATE': '3/27/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '284.0', 'LAST_UPDATEDBY': 'mb', 'POST': 'win', 'LASTENTRYDATE': '3/15/2014 15:00', 'TERMINAL_SUFFIX': 'mb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'seymour', 'NAMEFIRST': 'jasmine', 'NAMEMID': 'r', 'UIN': 'u57191', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '2/21/2014 0:00', 'APPT_START_DATE': '3/8/2014 7:30', 'APPT_END_DATE': '3/8/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '272.0', 'LAST_UPDATEDBY': 'lj', 'POST': 'win', 'LASTENTRYDATE': '2/21/2014 13:56', 'TERMINAL_SUFFIX': 'lj', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'alms', 'NAMEFIRST': 'andrea', 'NAMEMID': 't', 'UIN': 'u48801', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '1/24/2014 0:00', 'APPT_START_DATE': '1/24/2014 12:00', 'APPT_END_DATE': '1/24/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '1150.0', 'LAST_UPDATEDBY': 'lj', 'POST': 'win', 'LASTENTRYDATE': '1/24/2014 8:33', 'TERMINAL_SUFFIX': 'lj', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '4/25/2014'}, '1': {'NAMELAST': 'asher', 'NAMEFIRST': 'nathalie', 'NAMEMID': 'r', 'UIN': 'u55419', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41684', 'APPT_START_DATE': '41685.41667', 'APPT_END_DATE': '41685.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '237.0', 'LAST_UPDATEDBY': 'lj', 'POST': 'win', 'LASTENTRYDATE': '41684.46456', 'TERMINAL_SUFFIX': 'lj', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '5/30/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'burrows', 'NAMEFIRST': 'jessica', 'NAMEMID': 'a', 'UIN': 'u61754', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/10/2014 0:00', 'APPT_START_DATE': '3/22/2014 13:30', 'APPT_END_DATE': '3/22/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '276.0', 'LAST_UPDATEDBY': 'lj', 'POST': 'win', 'LASTENTRYDATE': '3/10/2014 12:52', 'TERMINAL_SUFFIX': 'lj', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'oppermann', 'NAMEFIRST': 'karleen', 'NAMEMID': 'c', 'UIN': 'u58507', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '2/26/2014 0:00', 'APPT_START_DATE': '3/12/2014 10:30', 'APPT_END_DATE': '3/12/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '273.0', 'LAST_UPDATEDBY': 'am', 'POST': 'win', 'LASTENTRYDATE': '2/26/2014 11:16', 'TERMINAL_SUFFIX': 'am', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'hector', 'NAMEFIRST': 'vargas', 'NAMEMID': 'g', 'UIN': 'u45265', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '1/3/2014 0:00', 'APPT_START_DATE': '1/9/2014 8:30', 'APPT_END_DATE': '1/9/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '263.0', 'LAST_UPDATEDBY': 'lj', 'POST': 'win', 'LASTENTRYDATE': '1/3/2014 16:46', 'TERMINAL_SUFFIX': 'lj', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '4/25/2014'}, '1': {'NAMELAST': 'weldon', 'NAMEFIRST': 'lauren', 'NAMEMID': 's', 'UIN': 'u48801', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '1/24/2014 0:00', 'APPT_START_DATE': '1/24/2014 12:00', 'APPT_END_DATE': '1/24/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '1150.0', 'LAST_UPDATEDBY': 'lj', 'POST': 'win', 'LASTENTRYDATE': '1/24/2014 8:38', 'TERMINAL_SUFFIX': 'lj', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '4/25/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'yeargin', 'NAMEFIRST': 'alexander', 'NAMEMID': 'g', 'UIN': 'u57228', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '2/22/2014 0:00', 'APPT_START_DATE': '3/8/2014 11:30', 'APPT_END_DATE': '3/8/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '275.0', 'LAST_UPDATEDBY': 'lj', 'POST': 'win', 'LASTENTRYDATE': '2/22/2014 14:25', 'TERMINAL_SUFFIX': 'lj', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'zigan', 'NAMEFIRST': 'lauren', 'NAMEMID': 'm', 'UIN': 'u64871', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/20/2014 0:00', 'APPT_START_DATE': '3/29/2014 10:30', 'APPT_END_DATE': '3/29/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '275.0', 'LAST_UPDATEDBY': 'am', 'POST': 'win', 'LASTENTRYDATE': '3/20/2014 6:40', 'TERMINAL_SUFFIX': 'am', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'feldstein', 'NAMEFIRST': 'steven', 'NAMEMID': 'j', 'UIN': 'u51535', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41680', 'APPT_START_DATE': '41681.3125', 'APPT_END_DATE': '41681.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '5707.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '41680.65991', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': None, 'visitee_namefirst': 'potus', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'south lawn', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, '1': {'NAMELAST': 'mervosh', 'NAMEFIRST': 'jeffrey', 'NAMEMID': 's', 'UIN': 'u51535', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41680', 'APPT_START_DATE': '41681.3125', 'APPT_END_DATE': '41681.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '5707.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '41680.66728', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': None, 'visitee_namefirst': 'potus', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'south lawn', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'chavez', 'NAMEFIRST': 'paul', 'NAMEMID': None, 'UIN': 'u64303', 'BDGNBR': '100169.0', 'ACCESS_TYPE': 'va', 'TOA': '3/19/2014 13:37', 'POA': 'd1101', 'TOD': '3/19/2014 17:00', 'POD': None, 'APPT_MADE_DATE': '3/18/2014 0:00', 'APPT_START_DATE': '3/19/2014 13:30', 'APPT_END_DATE': '3/19/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '153.0', 'LAST_UPDATEDBY': 'zh', 'POST': 'win', 'LASTENTRYDATE': '3/18/2014 14:18', 'TERMINAL_SUFFIX': 'zh', 'visitee_namelast': None, 'visitee_namefirst': 'potus', 'MEETING_LOC': 'oeob', 'MEETING_ROOM': 'sca', 'CALLER_NAME_LAST': 'hassan', 'CALLER_NAME_FIRST': 'zaid', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'scotland', 'NAMEFIRST': 'avalon', 'NAMEMID': 'a', 'UIN': 'u67757', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/28/2014 0:00', 'APPT_START_DATE': '3/31/2014 10:00', 'APPT_END_DATE': '3/31/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '132.0', 'LAST_UPDATEDBY': 'zh', 'POST': 'win', 'LASTENTRYDATE': '3/28/2014 18:42', 'TERMINAL_SUFFIX': 'zh', 'visitee_namelast': 'neri', 'visitee_namefirst': 'jorge', 'MEETING_LOC': 'oeob', 'MEETING_ROOM': 'sca', 'CALLER_NAME_LAST': 'hassan', 'CALLER_NAME_FIRST': 'zaid', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'vijums', 'NAMEFIRST': 'paul', 'NAMEMID': 'a', 'UIN': 'u52117', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41670', 'APPT_START_DATE': '41685.52083', 'APPT_END_DATE': '41685.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '280.0', 'LAST_UPDATEDBY': 'lj', 'POST': 'win', 'LASTENTRYDATE': '41670.70821', 'TERMINAL_SUFFIX': 'lj', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, '1': {'NAMELAST': 'lebed', 'NAMEFIRST': 'arianna', 'NAMEMID': 'o', 'UIN': 'u52117', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41670', 'APPT_START_DATE': '41685.52083', 'APPT_END_DATE': '41685.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '280.0', 'LAST_UPDATEDBY': 'lj', 'POST': 'win', 'LASTENTRYDATE': '41670.70789', 'TERMINAL_SUFFIX': 'lj', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'angotti', 'NAMEFIRST': 'frank', 'NAMEMID': 'n', 'UIN': 'u63714', 'BDGNBR': '0.0', 'ACCESS_TYPE': 'va', 'TOA': '3/15/2014 9:15', 'POA': 'vis01', 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/15/2014 0:00', 'APPT_START_DATE': '3/15/2014 9:17', 'APPT_END_DATE': '3/15/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '2.0', 'LAST_UPDATEDBY': 'jc', 'POST': 'win', 'LASTENTRYDATE': '3/15/2014 9:12', 'TERMINAL_SUFFIX': 'jc', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'trenerry', 'NAMEFIRST': 'amanda', 'NAMEMID': 'j', 'UIN': 'u46244', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '1/8/2014 0:00', 'APPT_START_DATE': '1/10/2014 8:00', 'APPT_END_DATE': '1/10/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '25.0', 'LAST_UPDATEDBY': 'mb', 'POST': 'win', 'LASTENTRYDATE': '1/8/2014 14:53', 'TERMINAL_SUFFIX': 'mb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '4/25/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'torres', 'NAMEFIRST': 'paula', 'NAMEMID': None, 'UIN': 'u62363', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/11/2014 0:00', 'APPT_START_DATE': '3/21/2014 13:30', 'APPT_END_DATE': '3/21/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '273.0', 'LAST_UPDATEDBY': 'mb', 'POST': 'win', 'LASTENTRYDATE': '3/11/2014 16:01', 'TERMINAL_SUFFIX': 'mb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'wittman', 'NAMEFIRST': 'mark', 'NAMEMID': 'a', 'UIN': 'u63229', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/13/2014 0:00', 'APPT_START_DATE': '3/20/2014 10:30', 'APPT_END_DATE': '3/20/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '285.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '3/13/2014 16:27', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'knight', 'NAMEFIRST': 'douglas', 'NAMEMID': 'k', 'UIN': 'u51535', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41680', 'APPT_START_DATE': '41681.3125', 'APPT_END_DATE': '41681.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '5707.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '41680.6648', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': None, 'visitee_namefirst': 'potus', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'south lawn', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, '1': {'NAMELAST': 'wu', 'NAMEFIRST': 'jodi', 'NAMEMID': None, 'UIN': 'u51535', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41680', 'APPT_START_DATE': '41681.3125', 'APPT_END_DATE': '41681.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '5707.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '41680.67619', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': None, 'visitee_namefirst': 'potus', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'south lawn', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'smith', 'NAMEFIRST': 'cameron', 'NAMEMID': 'r', 'UIN': 'u62712', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/12/2014 0:00', 'APPT_START_DATE': '3/26/2014 9:00', 'APPT_END_DATE': '3/26/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '294.0', 'LAST_UPDATEDBY': 'lj', 'POST': 'win', 'LASTENTRYDATE': '3/12/2014 14:48', 'TERMINAL_SUFFIX': 'lj', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'fore', 'NAMEFIRST': 'alyssa', 'NAMEMID': 'r', 'UIN': 'u58419', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '2/26/2014 0:00', 'APPT_START_DATE': '3/12/2014 8:30', 'APPT_END_DATE': '3/12/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '300.0', 'LAST_UPDATEDBY': 'am', 'POST': 'win', 'LASTENTRYDATE': '2/26/2014 9:12', 'TERMINAL_SUFFIX': 'am', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'barksdale', 'NAMEFIRST': 'laverne', 'NAMEMID': None, 'UIN': 'u64430', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/18/2014 0:00', 'APPT_START_DATE': '3/28/2014 10:30', 'APPT_END_DATE': '3/28/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '275.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '3/18/2014 17:08', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'prochnow', 'NAMEFIRST': 'kami', 'NAMEMID': 'l', 'UIN': 'u59884', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/4/2014 0:00', 'APPT_START_DATE': '3/13/2014 8:30', 'APPT_END_DATE': '3/13/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '297.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '3/4/2014 10:27', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'rudowske', 'NAMEFIRST': 'sheila', 'NAMEMID': 'm', 'UIN': 'u66806', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/26/2014 0:00', 'APPT_START_DATE': '3/28/2014 8:00', 'APPT_END_DATE': '3/28/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '262.0', 'LAST_UPDATEDBY': 'am', 'POST': 'win', 'LASTENTRYDATE': '3/26/2014 13:50', 'TERMINAL_SUFFIX': 'am', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'maghamez', 'NAMEFIRST': 'albert', 'NAMEMID': 'j', 'UIN': 'u44415', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '12/26/2013 0:00', 'APPT_START_DATE': '1/3/2014 11:00', 'APPT_END_DATE': '1/3/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '260.0', 'LAST_UPDATEDBY': 'jc', 'POST': 'win', 'LASTENTRYDATE': '12/26/2013 13:04', 'TERMINAL_SUFFIX': 'jc', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'f', 'RELEASE_DATE': '4/25/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'wrightsman', 'NAMEFIRST': 'john', 'NAMEMID': 'd', 'UIN': 'u63057', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/13/2014 0:00', 'APPT_START_DATE': '3/20/2014 7:30', 'APPT_END_DATE': '3/20/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '274.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '3/13/2014 11:43', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'shiller', 'NAMEFIRST': 'peter', 'NAMEMID': 's', 'UIN': 'u57188', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '2/21/2014 0:00', 'APPT_START_DATE': '3/1/2014 11:30', 'APPT_END_DATE': '3/1/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '275.0', 'LAST_UPDATEDBY': 'am', 'POST': 'win', 'LASTENTRYDATE': '2/21/2014 15:42', 'TERMINAL_SUFFIX': 'am', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'duplaga', 'NAMEFIRST': 'joseph', 'NAMEMID': 'r', 'UIN': 'u51535', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41680', 'APPT_START_DATE': '41681.3125', 'APPT_END_DATE': '41681.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '5707.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '41680.6594', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': None, 'visitee_namefirst': 'potus', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'south lawn', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, '1': {'NAMELAST': 'washburn', 'NAMEFIRST': 'kevin', 'NAMEMID': 'k', 'UIN': 'u51535', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '41680', 'APPT_START_DATE': '41681.3125', 'APPT_END_DATE': '41681.99931', 'APPT_CANCEL_DATE': None, 'Total_People': '5707.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '41680.67531', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': None, 'visitee_namefirst': 'potus', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'south lawn', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '5/30/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'dardery', 'NAMEFIRST': 'abdulmawgoud', 'NAMEMID': 'r', 'UIN': 'u59892', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/13/2014 0:00', 'APPT_START_DATE': '3/13/2014 9:30', 'APPT_END_DATE': '3/13/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '252.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '3/13/2014 8:00', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'moore', 'NAMEFIRST': 'audrey', 'NAMEMID': 't', 'UIN': 'u64430', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/18/2014 0:00', 'APPT_START_DATE': '3/28/2014 10:30', 'APPT_END_DATE': '3/28/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '275.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '3/18/2014 17:08', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'mcaleese', 'NAMEFIRST': 'james', 'NAMEMID': 'p', 'UIN': 'u67643', 'BDGNBR': '0.0', 'ACCESS_TYPE': 'va', 'TOA': '3/30/2014 13:18', 'POA': 'b0401', 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/28/2014 0:00', 'APPT_START_DATE': '3/30/2014 13:15', 'APPT_END_DATE': '3/30/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '3.0', 'LAST_UPDATEDBY': 'kk', 'POST': 'win', 'LASTENTRYDATE': '3/28/2014 14:37', 'TERMINAL_SUFFIX': 'kk', 'visitee_namelast': 'kinneen', 'visitee_namefirst': 'kelly', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'west wing', 'CALLER_NAME_LAST': 'kinneen', 'CALLER_NAME_FIRST': 'kelly', 'CALLER_ROOM': None, 'description': 'west wing tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'heynen', 'NAMEFIRST': 'jeff', 'NAMEMID': 'p', 'UIN': 'u59499', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '2/28/2014 0:00', 'APPT_START_DATE': '3/3/2014 16:30', 'APPT_END_DATE': '3/3/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '3.0', 'LAST_UPDATEDBY': 'kj', 'POST': 'win', 'LASTENTRYDATE': '2/28/2014 16:32', 'TERMINAL_SUFFIX': 'kj', 'visitee_namelast': 'liberante', 'visitee_namefirst': 'wendy', 'MEETING_LOC': 'neob', 'MEETING_ROOM': '10103', 'CALLER_NAME_LAST': 'johnson', 'CALLER_NAME_FIRST': 'kim', 'CALLER_ROOM': None, 'description': None, 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'boriwicz', 'NAMEFIRST': 'mark', 'NAMEMID': 'd', 'UIN': 'u61651', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/10/2014 0:00', 'APPT_START_DATE': '3/12/2014 8:00', 'APPT_END_DATE': '3/12/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '197.0', 'LAST_UPDATEDBY': 'lj', 'POST': 'win', 'LASTENTRYDATE': '3/10/2014 10:42', 'TERMINAL_SUFFIX': 'lj', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'kivlin', 'NAMEFIRST': 'karrington', 'NAMEMID': 'c', 'UIN': 'u59899', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/4/2014 0:00', 'APPT_START_DATE': '3/13/2014 10:30', 'APPT_END_DATE': '3/13/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '278.0', 'LAST_UPDATEDBY': 'cb', 'POST': 'win', 'LASTENTRYDATE': '3/4/2014 10:42', 'TERMINAL_SUFFIX': 'cb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, 'answer': 'n'}, {'0': {'NAMELAST': 'jones', 'NAMEFIRST': 'laura', 'NAMEMID': 'k', 'UIN': 'u62348', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '3/11/2014 0:00', 'APPT_START_DATE': '3/21/2014 9:00', 'APPT_END_DATE': '3/21/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '289.0', 'LAST_UPDATEDBY': 'mb', 'POST': 'win', 'LASTENTRYDATE': '3/11/2014 15:38', 'TERMINAL_SUFFIX': 'mb', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '6/27/2014'}, '1': {'NAMELAST': 'jones', 'NAMEFIRST': 'lauren', 'NAMEMID': None, 'UIN': 'u46340', 'BDGNBR': None, 'ACCESS_TYPE': 'va', 'TOA': None, 'POA': None, 'TOD': None, 'POD': None, 'APPT_MADE_DATE': '1/8/2014 0:00', 'APPT_START_DATE': '1/24/2014 11:00', 'APPT_END_DATE': '1/24/2014 23:59', 'APPT_CANCEL_DATE': None, 'Total_People': '113.0', 'LAST_UPDATEDBY': 'am', 'POST': 'win', 'LASTENTRYDATE': '1/8/2014 18:38', 'TERMINAL_SUFFIX': 'am', 'visitee_namelast': 'office', 'visitee_namefirst': 'visitors', 'MEETING_LOC': 'wh', 'MEETING_ROOM': 'residence', 'CALLER_NAME_LAST': 'office', 'CALLER_NAME_FIRST': 'visitors', 'CALLER_ROOM': None, 'description': 'group tour', 'RELEASE_DATE': '4/25/2014'}, 'answer': 'y'}]
        }

    results = find_duplicates_in_files(
        file_paths=input_files,
        config=config,
        training_data=None,
        # data
    )

    print(results)