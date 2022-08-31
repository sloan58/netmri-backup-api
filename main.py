import json
import logging
import os
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

import requests
from dotenv import load_dotenv
from infoblox_netmri import InfobloxNetMRI

load_dotenv()

base_dir = os.getcwd()
backup_dir = os.path.join(base_dir, 'backups', datetime.now().strftime("%Y-%m-%d"))
os.makedirs(backup_dir, exist_ok=True)

log_directory = os.path.join(base_dir, 'logs')
os.makedirs(log_directory, exist_ok=True)

filename = os.path.join(log_directory, datetime.now().strftime("%Y-%m-%d.log"))
logging.basicConfig(
    handlers=[RotatingFileHandler(filename, maxBytes=100000, backupCount=10)],
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p',
    encoding='utf-8',
    level=logging.DEBUG)

try:
    net_mri_client = InfobloxNetMRI(
        host=os.getenv('NETMRI_HOST'),
        username=os.getenv('NETMRI_USER'),
        password=os.getenv('NETMRI_PASSWORD')
    )
except requests.exceptions.ConnectionError as e:
    logging.error(
        f'main: Could not connect to NetMRI:', exc_info=True)
    exit()


tries = 0            # Current archive download try (initial 0)
max_tries = 3        # Max archive download ties
backoff_factor = 10  # Exponential backoff (tries * backoff_factor)


def initiate_archive():
    try:
        response = net_mri_client.api_request('system_backup/create_archive', {
            'init': True,
            'async_ind': True
        })
        logging.info(
            f'create_archive: Requested new db archive: Response: {response["message"]}')
    except requests.exceptions.HTTPError as e:
        message = json.loads(e.response.text)['message'] or ''
        logging.error(f'download_archive_md5_sum: Message: {message}')
        exit()


def download_archive():
    global tries, backoff_factor
    try:
        os.chdir(backup_dir)
        response = net_mri_client.api_request('system_backup/download_archive', {}, downloadable=True)
        logging.info(
            f'download_archive: Status of new archive download: Downloaded {response["Filename"]} {response["Status"]}')
    except requests.exceptions.HTTPError as e:
        message = json.loads(e.response.text)['message'] or ''
        logging.error(f'download_archive: message: {message}')
        if tries != max_tries:
            tries += 1
            logging.error(
                f'download_archive: Max tries {max_tries} not reached (tried {tries} times).  '
                f'Trying again after backoff {backoff_factor * tries}.'
            )
            time.sleep(backoff_factor * tries)
            download_archive()
        else:
            logging.error(f'download_archive: Max tries {max_tries} reached (tried {tries} times).  Exiting.')
            exit()


def download_archive_md5():
    try:
        response = net_mri_client.api_request('system_backup/download_archive_md5_sum', {}, downloadable=True)
        logging.info(
            f'download_archive_md5_sum: Status of new archive md5 download: Downloaded {response["Filename"]} {response["Status"]}')
    except requests.exceptions.HTTPError as e:
        message = json.loads(e.response.text)['message'] or ''
        logging.error(f'download_archive_md5_sum: Message: {message}.  Exiting.')


def delete_archive_on_server():
    try:
        response = net_mri_client.api_request('system_backup/remove_archive', {})
        logging.info(
            f'remove_archive: Response: {response["message"]}')
    except requests.exceptions.HTTPError as e:
        message = json.loads(e.response.text)['message'] or ''
        logging.error(f'remove_archive: Message: {message}.  Exiting.')


initiate_archive()
download_archive()
download_archive_md5()
delete_archive_on_server()
