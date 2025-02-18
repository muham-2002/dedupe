#Chala hua code
# import dedupe.variables
# import dedupe.variables.string
import dedupe.variables
import pandas as pd
import dedupe
from unidecode import unidecode
import re
import os
import json
import logging
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def preprocess(column):
    """Clean data using Unidecode and Regex"""
    if not column:
        return ""
    
    column = unidecode(str(column))
    # Replace 'nan' with ''
    if column.lower() == 'nan':
        return ""
        
    column = re.sub('  +', ' ', column)
    column = re.sub('\n', ' ', column)
    column = column.strip().strip('"').strip("'").lower().strip()
    return "" if not column else column

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
    Detect fields from the first file and create field configurations
    
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
        
        # Use all columns as potential match fields
        match_fields = columns
        
        return fields, match_fields
        
    except Exception as e:
        logger.error(f"Error detecting fields from file {file_path}: {str(e)}")
        raise

def find_duplicates_in_files(
    training_data,
    file_paths: List[str], 
    output_file: str = None, 
    settings_file: str = 'learned_settings',
    config: Dict = None,
) -> List[Dict]:
    """
    Find duplicates in one or more CSV or Excel files with configurable parameters
    Uses only first 400 rows for training but processes entire file for duplicates
    """
    # Set default configuration
    default_config = {
        'similarity_threshold': 0.5,
        'recall_weight': 1.0,
        'chunk_size': 100000,
        'fields': [],  # Will be populated from the first file
        'required_matches': 1,  # Default to requiring at least one match
        'max_training_matches': 5,  # Number of positive training examples
        'max_training_distincts': 5,  # Number of negative training examples
        'max_training_rows': 400  # Maximum rows to use for training
    }
    
    config = {**default_config, **(config or {})}
    
    # Validate input files
    for file_path in file_paths:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
    
    # Detect fields if not specified
    if not config['fields']:
        config['fields'], config['match_fields'] = detect_fields(file_paths[0])
    
    # Read all input files
    all_data = read_input_files(file_paths, config['chunk_size'])
    
    # Validate data is not empty
    if len(all_data) == 0:
        raise ValueError("No data found in input files")
    
    # Create a sample for training using first max_training_rows
    training_data_df = all_data.head(config['max_training_rows'])
    training_data_d = convert_df_to_dedupe_format(training_data_df)
    
    # Convert full data to dedupe format (will be used later for finding duplicates)
    full_data_d = convert_df_to_dedupe_format(all_data)
    
    # Print data summary
    logger.info("Data Summary:")
    logger.info(f"Total records: {len(all_data)}")
    logger.info(f"Records used for training: {len(training_data_df)}")
    for file_path in file_paths:
        file_data = all_data[all_data['source_file'] == os.path.basename(file_path)]
        logger.info(f"- {file_path}: {len(file_data)} records")
    
    # Convert field configurations to dedupe format
    variable_definition = []
    for field_config in config['fields']:
        field_type = field_config['type']
        field_name = field_config['field']
        has_missing = field_config.get('has_missing', False)
        
        if field_type == 'String':
            variable = dedupe.variables.String(field_name, has_missing=has_missing)
        elif field_type == 'Text':
            variable = dedupe.variables.Text(field_name, has_missing=has_missing)
        elif field_type == 'Price':
            variable = dedupe.variables.Price(field_name, has_missing=has_missing)
        elif field_type == 'DateTime':
            variable = dedupe.variables.DateTime(field_name, has_missing=has_missing)
        elif field_type == 'Exact':
            variable = dedupe.variables.Exact(field_name, has_missing=has_missing)
        else:
            variable = dedupe.variables.String(field_name, has_missing=has_missing)
            
        variable_definition.append(variable)

    # Initialize deduper
    logger.info("Training dedupe...")
    deduper = dedupe.Dedupe(variable_definition)
    
    # Use training data subset for prepare_training
    deduper.prepare_training(training_data_d)
    
    uncertain_pairs = []
    if training_data is None:
        try:
            while True:
                uncertain_pair = deduper.uncertain_pairs()
                if not uncertain_pair:
                    break
                uncertain_pairs.append(uncertain_pair[0])
        except IndexError:
            pass
            
        training_pairs = []
        for pair in uncertain_pairs:
            training_pairs.append({
                '0': pair[0],
                '1': pair[1]
            })

        # Get organized pairs using the new matching approach
        organized_pairs = find_top_matching_pairs(training_pairs, config)
        
        return {
            'pairs': organized_pairs,
            'status': 'needs_training'
        }
    else:
        # Convert provided training data to dedupe format
        formatted_pairs = {
            "match": [],
            "distinct": []
        }
        
        for pair in training_data:
            record_pair = (pair['0'], pair['1'])
            if pair['answer'] == 'y':
                formatted_pairs['match'].append(record_pair)
            elif pair['answer'] == 'n':
                formatted_pairs['distinct'].append(record_pair)
        
        logger.info(f"Training dedupe with {len(formatted_pairs['match'])} match pairs and {len(formatted_pairs['distinct'])} distinct pairs")
        # Train with provided data
        deduper.mark_pairs(formatted_pairs)
        deduper.train()
        
        # Now use the trained model on the full dataset
        logger.info("Finding duplicates in full dataset...")
        threshold = config['similarity_threshold']
        logger.info(f"Using threshold: {threshold}")
        
        # Process in chunks of 10000
        chunk_size = 1000
        results = []
        cluster_membership = {}
        total_clusters = 0
        
        # Process data in chunks
        for i in range(0, len(all_data), chunk_size):
            chunk_end = min(i + chunk_size, len(all_data))
            logger.info(f"Processing records {i} to {chunk_end} of {len(all_data)}")
            
            # Get chunk of data
            chunk_keys = list(full_data_d.keys())[i:chunk_end]
            chunk_data = {k: full_data_d[k] for k in chunk_keys}
            
            # Find duplicates in this chunk
            chunk_dupes = deduper.partition(chunk_data, threshold)
            
            # Process results from this chunk
            for records, scores in chunk_dupes:
                if len(records) > 1:  # Only include actual duplicates
                    cluster_records = []
                    
                    # Save cluster membership for each record
                    for record_id, score in zip(records, scores):
                        cluster_membership[record_id] = {
                            "cluster_id": total_clusters,
                            "confidence_score": score
                        }
                        
                        record = full_data_d[record_id].copy()
                        record.update({
                            'confidence_score': score,
                            'source_file': all_data.loc[int(record_id), 'source_file'],
                            'record_id': record_id
                        })
                        cluster_records.append(record)
                    
                    # Add all clusters without additional checks
                    results.append({
                        'cluster_id': total_clusters,
                        'group_size': len(cluster_records),
                        'confidence_score': sum(r['confidence_score'] for r in cluster_records) / len(cluster_records),
                        'records': cluster_records
                    })
                    total_clusters += 1

        logger.info(f"Found {len(results)} duplicate groups across all chunks")
        results = sorted(results, key=lambda x: x['confidence_score'], reverse=True)
        
        # Save results if output file is specified
        if output_file:
            # Convert numpy float32 values to native Python floats for JSON serialization
            json_results = []
            for result in results:
                result_copy = result.copy()
                result_copy['confidence_score'] = float(result_copy['confidence_score'])
                records = []
                for record in result_copy['records']:
                    record_copy = record.copy()
                    record_copy['confidence_score'] = float(record_copy['confidence_score'])
                    records.append(record_copy)
                result_copy['records'] = records
                json_results.append(result_copy)

            with open(output_file, 'w') as f:
                json.dump({
                    'total_records': len(all_data),
                    'duplicate_groups_found': len(results),
                    'duplicates': json_results,
                    'configuration': config,
                    'threshold_used': float(threshold)
                }, f, indent=2)
            logger.info(f"Results saved to {output_file}")
        
        return results

def find_top_matching_pairs(training_pairs: List[Dict], config: Dict) -> List[Dict]:
    """
    Organize training pairs by alternating between matching, random, and distinct pairs
    
    Args:
        training_pairs: List of training pair objects, each containing '0' and '1' records
        config: Configuration dictionary with selected_columns list
    
    Returns:
        List of organized training pairs alternating between matching, random, and distinct
    """
    if not training_pairs:
        return []
        
    # Get columns to match from config, fallback to first two if not specified
    sample_record = training_pairs[0]['0']
    match_columns = config.get('selected_columns', list(sample_record.keys())[:2])
    
    # Categorize pairs based on selected columns
    matching_pairs = []
    distinct_pairs = []
    
    for pair in training_pairs:
        match_score = 0
        for field in match_columns:
            val1 = str(pair['0'].get(field, '')).lower().strip()
            val2 = str(pair['1'].get(field, '')).lower().strip()
            if val1 and val2 and val1 == val2:
                match_score += 1
        
        if match_score == len(match_columns):  # All selected columns match
            matching_pairs.append(pair)
        elif match_score == 0:  # No columns match
            distinct_pairs.append(pair)
    
    # Remaining pairs will be used as random pairs
    random_pairs = [p for p in training_pairs 
                   if p not in matching_pairs and p not in distinct_pairs]
    
    # Organize pairs in the desired pattern: matching, random, distinct
    organized_pairs = []
    max_length = max(len(matching_pairs), len(random_pairs), len(distinct_pairs))
    
    for i in range(max_length):
        # Add a matching pair if available
        if i < len(matching_pairs):
            organized_pairs.append(matching_pairs[i])
            
        # Add a random pair if available
        if i < len(random_pairs):
            organized_pairs.append(random_pairs[i])
            
        # Add a distinct pair if available
        if i < len(distinct_pairs):
            organized_pairs.append(distinct_pairs[i])
    
    # Add any remaining pairs to maintain all training data
    remaining_matches = matching_pairs[max_length:]
    remaining_random = random_pairs[max_length:]
    remaining_distinct = distinct_pairs[max_length:]
    
    organized_pairs.extend(remaining_matches)
    organized_pairs.extend(remaining_random)
    organized_pairs.extend(remaining_distinct)
    
    return organized_pairs

if __name__ == "__main__":
    # Example usage with optimized configuration
    # input_files = ['KNA1.xlsx']  # Your input file
    input_files = ['KNA2.xlsx']
    output_file = 'duplicate_results.json'
    settings_file = 'learned_settings'
    
    # Force retraining by removing existing settings
    force_retrain = False  # Set to True to force retraining, False to use existing settings
    
    # Optimized configuration for better duplicate detection
    config = {
        'similarity_threshold': 0.0,    # No threshold to catch all potential duplicates
        'required_matches': 1,          # Require at least one field to match
        'chunk_size': 50000,           # For handling large files
        'max_training_matches': 5,      # Training examples
        'max_training_distincts': 5,    # Training examples
        'recall_weight': 1.0           # Maximum recall to catch all potential duplicates
    }
    
    try:
        # Use the find_duplicates_in_files function

        data = {
            "pairs": [
                {
            "0": {
                "Customer": "210019",
                "Name 1": "hapis sp zoo",
                "Name 2": "nan",
                "Street": "moniuszki 18",
                "Postal Code": "12-100",
                "City": "szczytno",
                "Region": "nan",
                "Country": "pl",
            },
            "1": {
                "Customer": "210019",
                "Name 1": "hapis sp zoo",
                "Name 2": "nan",
                "Street": "moniuszki 18",
                "Postal Code": "12-100",
                "City": "szczytno",
                "Region": "nan",
                "Country": "pl",
            },
            "answer": "y"
        },
               {
            "0": {
                "Customer": "210019",
                "Name 1": "hapis sp zoo",
                "Name 2": "nan",
                "Street": "moniuszki 18",
                "Postal Code": "12-100",
                "City": "szczytno",
                "Region": "nan",
                "Country": "pl",
            },
            "1": {
                "Customer": "210019",
                "Name 1": "hapis sp zoo",
                "Name 2": "nan",
                "Street": "moniuszki 18",
                "Postal Code": "12-100",
                "City": "szczytno",
                "Region": "nan",
                "Country": "pl",
            },
            "answer": "y"
        },
               {
            "0": {
                "Customer": "210019",
                "Name 1": "hapis sp zoo",
                "Name 2": "nan",
                "Street": "moniuszki 18",
                "Postal Code": "12-100",
                "City": "szczytno",
                "Region": "nan",
                "Country": "pl",
            },
            "1": {
                "Customer": "210019",
                "Name 1": "hapis sp zoo",
                "Name 2": "nan",
                "Street": "moniuszki 18",
                "Postal Code": "12-100",
                "City": "szczytno",
                "Region": "nan",
                "Country": "pl",
            },
            "answer": "y"
        },
               {
            "0": {
                "Customer": "210019",
                "Name 1": "hapis sp zoo",
                "Name 2": "nan",
                "Street": "moniuszki 18",
                "Postal Code": "12-100",
                "City": "szczytno",
                "Region": "nan",
                "Country": "pl",
            },
            "1": {
                "Customer": "210019",
                "Name 1": "hapis sp zoo",
                "Name 2": "nan",
                "Street": "moniuszki 18",
                "Postal Code": "12-100",
                "City": "szczytno",
                "Region": "nan",
                "Country": "pl",
            },
            "answer": "y"
        },
               {
            "0": {
                "Customer": "210019",
                "Name 1": "hapis sp zoo",
                "Name 2": "nan",
                "Street": "moniuszki 18",
                "Postal Code": "12-100",
                "City": "szczytno",
                "Region": "nan",
                "Country": "pl",
            },
            "1": {
                "Customer": "210019",
                "Name 1": "hapis sp zoo",
                "Name 2": "nan",
                "Street": "moniuszki 18",
                "Postal Code": "12-100",
                "City": "szczytno",
                "Region": "nan",
                "Country": "pl",
            },
            "answer": "n"
        },
            ],
        }

        results = find_duplicates_in_files(
            file_paths=input_files,
            config=config,
            training_data=data
        )

        
        print(results)
        
        if not results:
            print("\nNo duplicates found with current settings.")
            print("\nTroubleshooting steps:")
            print("1. Check your data for actual duplicates")
            print("2. Try adjusting the similarity threshold (current: 0.0)")
            print("3. Try with force_retrain = True")
            
            # Show sample data
            try:
                print("\nData sample from first file:")
                if input_files[0].endswith(('.xlsx', '.xls')):
                    sample = pd.read_excel(input_files[0], nrows=2)
                else:
                    sample = pd.read_csv(input_files[0], nrows=2)
                print(sample.to_string())
            except Exception as sample_error:
                print(f"Could not read data sample: {str(sample_error)}")
        else:
            print(f"\nFound {len(results)} groups of duplicates")
            
            # Print first few duplicate groups
            for i, group in enumerate(results[:3], 1):
                print(f"\nDuplicate Group {i}:")
                print(f"Confidence Score: {group['confidence_score']:.2f}")
                print(f"Number of Records: {group['group_size']}")
                print("\nRecords:")
                for record in group['records']:
                    print(f"\nFrom {record['source_file']}:")
                    for k, v in record.items():
                        if k not in ['confidence_score', 'source_file', 'record_id']:
                            print(f"  {k}: {v}")
            
            print("\nTo use these settings in future runs:")
            print("1. Set force_retrain = False")
            print(f"2. Keep using the same settings_file: '{settings_file}'")
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Print more detailed error information
        if "training_pairs" in str(e):
            print("\nTroubleshooting tips:")
            print("1. Check if your data has enough potential duplicates")
            print("2. Verify the column names in your files")
            print("3. Try adjusting the 'required_matches' parameter")
            print("4. Ensure the data preprocessing is working correctly") 
