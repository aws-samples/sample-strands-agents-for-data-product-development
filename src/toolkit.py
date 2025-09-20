


import json
import os
import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import logging
from pathlib import Path
import yaml
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor
import csv
import re
from strands import Agent, tool
import subprocess
import sys

# @tool
# def get_shared_state_info() -> str:
#     """
#     Get current shared state information.
    
#     Returns:
#         JSON string of current shared state
#     """
#     state_info = {
#         'current_step': shared_state.current_step,
#         'available_artifacts': list(shared_state.data.keys()),
#         'conversation_count': len(shared_state.conversation_history)
#     }
#     return json.dumps(state_info, indent=2)

@tool
def pipe_delimited_string_to_csv(
    schema_content: str,
    data_model_output_folder: str,
    file_prefix: str = "table",
    detect_tables: bool = True,
    single_output_file: Optional[str] = None
) -> Dict[str, str]:
    """
    Converts pipe-delimited string data to CSV file(s).
    
    Args:
        schema_content: Pipe-delimited string with "\n" as line separators
        data_model_output_folder: Folder to save CSV files (default: "output")
        file_prefix: Prefix for generated file names (default: "table")
        detect_tables: Whether to detect multiple tables (default: True)
        single_output_file: If provided, saves all content to this single file
        
    Returns:
        Dictionary mapping table names to their saved file paths
    """
    print("**** Calling pipe_delimited_string_to_csv tool ****")
    def extract_tables(content: str) -> Dict[str, str]:
        """
        Extracts multiple tables from the content by identifying table headers.
        
        Args:
            content: Pipe-delimited string content
            
        Returns:
            Dictionary mapping table names to their content
        """
        tables = {}
        
        # Split into lines
        lines = content.strip().split('\n')
        
        # Identify potential table headers (e.g., "#### Table_Name" or "| Table Name |")
        current_table = "Table_1"
        current_content = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Check if line is a header (markdown style)
            header_match = re.match(r'^#+\s+(.*?)\s*$', line)
            if header_match:
                # Save previous table if it has content
                if current_content:
                    tables[current_table] = '\n'.join(current_content)
                    current_content = []
                
                current_table = header_match.group(1).strip()
                continue
            
            # Also check for table name in the format "| Table Name |"
            if line.startswith('| ') and ' |' in line and not '|-' in line:
                # If this looks like a table header and the next line isn't a separator,
                # it might be a new table
                if current_content and len(current_content) > 1 and not current_content[-1].startswith('|'):
                    tables[current_table] = '\n'.join(current_content)
                    current_content = []
                    current_table = line.strip('| ').strip()
            
            # Add line to current table content
            current_content.append(line)
        
        # Add the last table
        if current_content:
            tables[current_table] = '\n'.join(current_content)
        
        return tables

    def save_table_content(table_content: str, csvfile) -> None:
        """
        Processes and saves pipe-delimited table content to a CSV file.
        
        Args:
            table_content: Pipe-delimited table content
            csvfile: File object to write to
        """
        # Split into lines and filter out empty lines
        lines = [line.strip() for line in table_content.split('\n') if line.strip()]
        
        csv_writer = csv.writer(csvfile)
        
        for line in lines:
            # Skip markdown table formatting lines
            if line.startswith('|') and '-+-' in line or all(c in '|-+' for c in line.strip()):
                continue
            
            # Process pipe-delimited line
            if line.startswith('|') and line.endswith('|'):
                # Extract cells, strip whitespace
                cells = [cell.strip() for cell in line.strip('|').split('|')]
                csv_writer.writerow(cells)
            else:
                # For non-pipe lines, just write as a single cell
                csv_writer.writerow([line])

    # Replace escaped newlines with actual newlines
    content = schema_content.replace("\\n", "\n")
    
    # Create output directory if it doesn't exist
    if not os.path.exists(data_model_output_folder):
        os.makedirs(data_model_output_folder)
    
    # Process the content
    if detect_tables:
        tables = extract_tables(content)
    else:
        tables = {"single_table": content}
    
    saved_files = {}
    
    # If single output file is specified
    if single_output_file:
        full_path = os.path.join(data_model_output_folder, single_output_file)
        with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
            for table_name, table_content in tables.items():
                # Add table name as a header
                csvfile.write(f"# {table_name}\n")
                
                # Process and write the table content
                save_table_content(table_content, csvfile)
                
                # Add a separator between tables
                csvfile.write("\n\n")
            
            saved_files["combined"] = full_path
    else:
        # Process each table separately
        for i, (table_name, table_content) in enumerate(tables.items()):
            # Create a valid filename from table name
            if table_name == "single_table":
                filename = f"{file_prefix}.csv"
            else:
                # Clean the table name to create a valid filename
                clean_name = re.sub(r'[^\w\s-]', '', table_name).strip().lower()
                clean_name = re.sub(r'[-\s]+', '_', clean_name)
                
                if clean_name:
                    filename = f"{file_prefix}_{clean_name}.csv"
                else:
                    filename = f"{file_prefix}_{i+1}.csv"
            
            full_path = os.path.join(data_model_output_folder, filename)
            
            with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
                save_table_content(table_content, csvfile)
            
            saved_files[table_name] = full_path
    
    return saved_files


@tool
def extract_csv_schemas(
    source_data_folder_path: str,
    sample_rows: int = 100,
    encoding: str = 'utf-8',
    csv_kwargs: Optional[Dict] = None
) -> Dict:
    """
    Recursively reads all CSV files in a folder and extracts schema information.
    
    Args:
        source_data_folder_path: Path to the folder containing CSV files
        sample_rows: Number of rows to sample for inferring data types (default: 100)
        encoding: Character encoding of the CSV files (default: 'utf-8')
        csv_kwargs: Additional keyword arguments to pass to pd.read_csv
        
    Returns:
        Dictionary mapping file paths to schema information dictionaries
    """
    print("**** Calling extract_csv_schema tool **** ")
    if not os.path.exists(source_data_folder_path):
        raise FileNotFoundError(f"The folder '{source_data_folder_path}' does not exist")
    
    if not os.path.isdir(source_data_folder_path):
        raise NotADirectoryError(f"'{source_data_folder_path}' is not a directory")
    
    if csv_kwargs is None:
        csv_kwargs = {}
    
    schemas = {}
    
    # Walk through all subdirectories
    for root, _, files in os.walk(source_data_folder_path):
        # Filter for CSV files
        csv_files = [f for f in files if f.lower().endswith('.csv')]
        
        for csv_file in csv_files:
            file_path = os.path.join(root, csv_file)
            try:
                # Read the header and a sample of rows to infer schema
                # Use nrows parameter to limit the number of rows read for large files
                df = pd.read_csv(file_path, encoding=encoding, nrows=sample_rows, **csv_kwargs)
                
                # Extract schema information
                file_schema = {
                    'file_path': file_path,
                    'columns': list(df.columns),
                    'num_columns': len(df.columns),
                    'dtypes': {col: str(df[col].dtype) for col in df.columns},
                    'sample_size': min(len(df), sample_rows),
                    'has_header': True,  # Assuming all CSVs have headers
                    'null_counts': {col: int(df[col].isna().sum()) for col in df.columns},
                    'unique_counts': {col: int(df[col].nunique()) for col in df.columns},
                    'example_values': {col: df[col].dropna().head(3).tolist() if not df[col].empty else [] 
                                      for col in df.columns}
                }
                
                # Store schema with relative path as the key
                rel_path = os.path.relpath(file_path, source_data_folder_path)
                schemas[rel_path] = file_schema
                
                print(f"Successfully extracted schema for: {rel_path}")
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
                # Add basic error information to the schema dictionary
                rel_path = os.path.relpath(file_path, source_data_folder_path)
                schemas[rel_path] = {
                    'file_path': file_path,
                    'error': str(e),
                    'status': 'failed'
                }
    
    return schemas


@tool
def save_generated_code(content: str, code_location:str) -> str:
    """Save the generated code in a local file for debugging purposes later on.
    """
    from pathlib import Path
    import re
    print("saving generated code")
    pattern = r"```python\n(.*?)\n```"

    # Extracting the Python code
    match = re.search(pattern, content, re.DOTALL)
    if match:
        python_code = match.group(1)
        print("Found your python code")
    else:
        print(f"could not extract code, code provided was \n{content}")
        python_code = content
        count = len(python_code)

    Path(code_location).write_text(python_code)
    print(f"after saving generated code, char count = {count}")
    return "generated code has been saved, ready to execute this code if required"




@tool
def check_and_execute_python_file(file_path):
    """
    Check if a Python file exists in specified folder and execute it.
    
    Args:
        folder_path (str): Path to the folder
    Returns:
        tuple: (success, errors, output) - Boolean success status, list of errors, command output
    """
    errors = []
    output = ""
    file_path = os.path.join(file_path)

    print(file_path)
    # Check if folder and file exist
    if not os.path.isfile(file_path):
        errors.append(f"File not found '{file_path}'")
        return False, errors, output
    
    folder_path = os.path.dirname(file_path)
    venv_path = os.path.join(folder_path, "venv")

    result = subprocess.run(
        [sys.executable, "-m", "venv", venv_path],
        capture_output=True,
        text=True,
        check=True
    )

    # Execute the Python file
    try:
        # Use sys.executable to ensure we use the same Python interpreter
        result = subprocess.run(
            ["bash", "-c", f"source {venv_path}/bin/activate && pip install pandas numpy && python {file_path}"], 
            capture_output=True, 
            text=True,
            check=True
        )
        output = result.stdout
        return True, errors, output
    except subprocess.CalledProcessError as e:
        errors.append(f"Execution failed (code {e.returncode}): {e.stderr}")
        return False, errors, e.stdout
    except Exception as e:
        errors.append(f"Failed to execute: {str(e)}")
        return False, errors, output
    

