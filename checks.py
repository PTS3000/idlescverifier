import requests
from web3 import Web3
import csv
import json
import os
import subprocess
import re
from tqdm import tqdm
import shutil
import time

contract_address = "0xCF3C8Be2e2C42331Da80EF210e9B1b307C03d36A"
api_key = "PHPT98HXQFDT5JR3B8GMDXWMX4WB5XDZTZ"
infura_url = "https://mainnet.infura.io/v3/f0182675f6074f63bcbf8c9bfae41671"
file_path= "new_contracts.csv"


def fetch_code(api_key,contract_address):
    api_url = f"https://api.etherscan.io/api?module=contract&action=getsourcecode&address={contract_address}&apikey={api_key}"

    response = requests.get(api_url)
    data = response.json()
    if data['status'] == '0':
        return None
    else:     
        contract_code = data['result'][0]['SourceCode']
        return contract_code



def update_db(file_path, new_string):
    with open(file_path, 'r', newline='') as csvfile:
        csvreader = csv.reader(csvfile)
        for row in csvreader:
            if len(row) > 0 and row[0] == new_string:
                print(f'String "{new_string}" already exists in {file_path}')
                return

    with open(file_path, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow([new_string])
    print(f'{new_string} added to {file_path}')




def get_latest_sc(infura_url, api_key):
    web3 = Web3(Web3.HTTPProvider(infura_url))

    if web3.provider:
        print("Connected to Ethereum node")
    else:
        print("Failed to connect to Ethereum node")
        exit()

    latest_block_number = web3.eth.block_number
    print(f"Latest Block Number: {latest_block_number}")

    latest_block = web3.eth.get_block(latest_block_number)
    total_transactions = len(latest_block['transactions'])

    with tqdm(total=total_transactions, desc="Scanning Transactions") as pbar:
        for tx_hash in latest_block['transactions']:
            tx_receipt = web3.eth.get_transaction_receipt(tx_hash)

            if tx_receipt is not None and tx_receipt['contractAddress'] is not None:
                print(f"Smart Contract Deployed at: {tx_receipt['contractAddress']}")
                tx = web3.eth.get_transaction(tx_hash)
                creator = tx['from']
                print(f"Created by: {creator}")
                update_db(file_path, tx_receipt['contractAddress'])

                return tx_receipt['contractAddress'], creator

            pbar.update(1)




#creates a new .sol file with the smart contract code
def store_new_sc(file_path, content):
    with open(file_path, 'w') as sol_file:
        sol_file.write(content)

def isnt_sourced(csv_file, target_string):
    with open(csv_file, 'r') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            if target_string in row[0]:
                return False
    return True





def iterate_csv_and_source(file_path):
    results = []
    
    with open(file_path, 'r', newline='') as csvfile:
        csvreader = csv.reader(csvfile)
        for row in csvreader:
            #check if row is not empty
            if not all(not cell.strip() for cell in row) and isnt_sourced('sourced_contracts.csv', row[0]):

                dt = fetch_code(api_key, row[0])
                if dt is not None:
                    store_new_sc(f"{row[0]}.sol", dt)
                    if set_solc_version(f"{row[0]}.sol"):
                        update_db('sourced_contracts.csv', f"{row[0]}")
                    else:
                        remove_file(f"{row[0]}.sol")
        
    
    return results




def iterate_csv_and_analyze(file_path):
    
    with open(file_path, 'r', newline='') as csvfile:
        csvreader = csv.reader(csvfile)
        for row in csvreader:
            if isnt_sourced('analyzed_contracts.csv', row[0]):
                run_slither_checks_and_store_report(f'{row[0]}.sol', f'{row[0]}.json')
                filter_json_response(f'{row[0]}.json', f'{row[0]}.md')
                remove_file(f'{row[0]}.json')
                move_file_to_folder(f'{row[0]}.md', 'results')
                remove_file(f'{row[0]}.sol')
                filter_and_save_csv('sourced_contracts.csv', 'analyzed_contracts.csv', row[0])
        



def remove_file(file_path):
    try:
        os.remove(file_path)
        print(f"File {file_path} removed successfully.")
    except OSError as e:
        print(f"Error removing file {file_path}: {e}")




def set_solc_version(file_path):
    try:
        # Read the contents of the .sol file
        with open(file_path, 'r') as sol_file:
            content = sol_file.read()

        # Use regular expressions to find the pragma statement and extract the version
        match = re.search(r'pragma solidity (\d+\.\d+\.\d+);', content)
        if match:
            solidity_version = match.group(1)

            # Install the specified Solidity version using solc-select
            install_command = f'solc-select install {solidity_version}'
            subprocess.run(install_command, shell=True, check=True)

            # Set the SOLC_VERSION environment variable
            export_command = f'export SOLC_VERSION={solidity_version}'
            subprocess.run(export_command, shell=True, check=True)

            print(f'Solidity version {solidity_version} set successfully.')
            return True
        else:
            print('Solidity version not found in pragma statement.')
            return False
            

    except Exception as e:
        print(f'Error: {e}')





def run_slither_checks_and_store_report(contract_file_path, output_report_path):
    try:
        # Run Slither checks and capture the JSON report
        cmd = f"slither {contract_file_path} --json {output_report_path}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)

        print(f"Slither report for {contract_file_path} saved as {output_report_path}")

    except subprocess.CalledProcessError as e:
        print(f"Error running Slither: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")





def filter_json_response(json_response, output_file):
    with open(json_response, 'r') as file:
        data = json.load(file)

    results = data.get("results")
    detectors = results.get("detectors")

    with open(output_file, 'w') as markdown_file:
        for detector in detectors:
            description = detector.get("description", "")
            impact = detector.get("impact", "")
            confidence = detector.get("confidence", "")
            check = detector.get("check", "")

            # Write a line of separation between detectors
            markdown_file.write("---\n")

            # Write the description with higher text size or bold
            markdown_file.write(f"**Description:** {description}\n")

            # Write the impact, confidence, and check parameters
            markdown_file.write(f"Impact: {impact}\n")
            markdown_file.write(f"Confidence: {confidence}\n")
            markdown_file.write(f"Check: {check}\n\n")




def move_file_to_folder(source_file, destination_folder):
    try:
        # Check if the source file exists
        if not os.path.isfile(source_file):
            raise FileNotFoundError(f"The file '{source_file}' does not exist.")

        # Check if the destination folder exists
        if not os.path.exists(destination_folder):
            raise FileNotFoundError(f"The destination folder '{destination_folder}' does not exist.")

        # Use shutil.move to move the file to the destination folder
        shutil.move(source_file, os.path.join(destination_folder, os.path.basename(source_file)))

        print(f"File '{source_file}' moved to '{destination_folder}' successfully.")
    except Exception as e:
        print(f"Error moving file: {e}")




def filter_and_save_csv(input_file, output_file, content_to_eliminate):
    # Open the input and output CSV files
    with open(input_file, 'r', newline='') as input_csv, \
         open(output_file, 'w', newline='') as output_csv:

        # Create CSV reader and writer objects
        csv_reader = csv.reader(input_csv)
        csv_writer = csv.writer(output_csv)

        # Iterate through rows in the input CSV
        for row in csv_reader:
            # Check if the content_to_eliminate is not in the row
            if content_to_eliminate in row:
                # Write the row to the output CSV
                csv_writer.writerow(row)



while True:
    #get the latest smart contracts deployed in the blockchain and store them in a file 
    get_latest_sc(infura_url, api_key)

    #periodically check list of new contracts and check if the source code is already available, in the case it is, 
    #store the source code in a sol file and remove the smart contract address from the list of new contracts
    iterate_csv_and_source("new_contracts.csv")

    #iterate through the list of smart contracts for which  we have sourced the code and run slither checks on all of them,
    #storing the raw json response in a file CONTRACT_ADDRESS.sol. It also filters the response and presents a markdown file
    #with the most important parts
    iterate_csv_and_analyze('sourced_contracts.csv')

    

    


