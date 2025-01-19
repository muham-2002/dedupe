#Chala hua code
import dedupe.variables
import dedupe.variables.string
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
    match_fields = config.get('match_fields', ['email', 'phone'])  # Default to email and phone
    
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
    
    logger.info(f"Generated {len(training_pairs['match'])} matching pairs and {len(training_pairs['distinct'])} distinct pairs")
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
    
    Args:
        file_paths: List of paths to CSV or Excel files
        output_file: Path to save results (optional)
        settings_file: Path to save/load learned settings
        config: Configuration dictionary
        training_data: Optional dictionary containing training pairs with answers
                      Format: {
                          'pairs': [
                              {
                                  '0': record1_dict,
                                  '1': record2_dict,
                                  'answer': 'y' | 'n' | 'u'
                              },
                              ...
                          ]
                      }
    """
    # Set default configuration
    default_config = {
        'similarity_threshold': 0.5,
        'recall_weight': 1.0,
        'chunk_size': 100000,
        'fields': [],  # Will be populated from the first file
        'required_matches': 1,  # Default to requiring at least one match
        'max_training_matches': 5,  # Number of positive training examples
        'max_training_distincts': 5  # Number of negative training examples
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
    
    # Print data summary
    logger.info("Data Summary:")
    for file_path in file_paths:
        file_data = all_data[all_data['source_file'] == os.path.basename(file_path)]
        logger.info(f"- {file_path}: {len(file_data)} records")
    
    # Convert data to dedupe format
    data_d = convert_df_to_dedupe_format(all_data)
    
    # Convert field configurations to dedupe format
    variable_definition = []
    for field_config in config['fields']:
        from dedupe._typing import VariableDefinition
        field_def: VariableDefinition = {
            'field': field_config['field'],
            'type': field_config['type'],
            'has_missing': field_config.get('has_missing', False)
        }
        variable_definition.append(field_def)
    
    # Initialize deduper
    logger.info("Training dedupe...")
    deduper = dedupe.Dedupe(variable_definition)
    deduper.prepare_training(data_d)
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

        return {
            'pairs': training_pairs,
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
            # Skip uncertain answers ('u')
        
        # Train with provided data
        deduper.mark_pairs(formatted_pairs)
        deduper.train()
        
        # Continue with finding duplicates
        logger.info("Finding duplicates...")
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
