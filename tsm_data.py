import logging
import requests
import json
import os
from time import time
from tqdm import tqdm

FILE_DIR = __file__.rsplit("\\", 1)[0] + "\\"
TSM_PRICE = "https://pricing-api.tradeskillmaster.com/"
TSM_AUTH = "https://auth.tradeskillmaster.com/oauth2/token"


def get_tsm_header():
	logging.debug(f"Reading required/tsm_credentials.txt")
	with open(FILE_DIR + "required/tsm_credentials.txt") as c:
		line = c.readline()
		stuff = {
			"client_id": "c260f00d-1071-409a-992f-dda2e5498536",
			"grant_type": "api_token",
			"scope": "app:realm-api app:pricing-api",
			"token": line
		}
	
	x = requests.post(
		TSM_AUTH, 
		data=stuff)
	logging.debug("TSM bearer token obtained")
	r = json.loads(x.text)
	if not r.get("access_token", False):
		raise KeyError("Error getting access token from TSM")

	return {"Authorization": "Bearer " + r["access_token"]}

def get_tsm_data(region, expire_time=86400*2):
	try:
		logging.debug("Reading local/tsm_data.json")
		with open(FILE_DIR + "local/tsm_data.json") as f:
			tsm_data = json.load(f)
			if tsm_data["date"] + expire_time > time():
				logging.debug("Local TSM data still fresh, reusing")
				return tsm_data
	except FileNotFoundError:
		logging.debug("No local data found, redownloading")
		pass
	except json.decoder.JSONDecodeError:
		logging.debug("Local data corrupted, redownloading")
		pass

	region = region.upper()
	match region:
		case "NA": r = 1
		case "EU": r = 2
	
	try:
		bearer = get_tsm_header()
		logging.info("Downloading TSM AH data")
		tsm_resp = requests.get(f"{TSM_PRICE}region/{r}", headers=bearer) #, stream=True
	except requests.exceptions.ConnectionError:
		logging.error("Connection error when attempting to get tsm data, check your internet connection")
		return False
	except FileNotFoundError:
		logging.warning("required/tsm_credentials.txt missing, proceeding without tsm data")
		return False
	if tsm_resp.status_code != 200:
		logging.error("Failed to get TSM data")
		logging.error(tsm_resp)
		logging.error(tsm_resp.reason)
		return False
	
	items = json.loads(tsm_resp.text)

	logging.debug(f"Parsing TSM data for {region}")
	tsm_data = {"date": time()}
	for entry in items:
		if entry["itemId"]:
			tsm_data[str(entry["itemId"])] = entry["marketValue"]
		elif entry["petSpeciesId"]:
			tsm_data["P" + str(entry["petSpeciesId"])] = entry["marketValue"]
	logging.info(f"Parsed TSM data for {region}, {len(tsm_data)-1} entries")

	os.makedirs(FILE_DIR+"local", exist_ok=True)
	with open(FILE_DIR + "local/tsm_data.json", "w") as f:
		json.dump(tsm_data, f, indent="\t")
		logging.debug(f"Wrote TSM data to local/tsm_data.json")
	return tsm_data

if __name__ == '__main__':
	logging.getLogger().setLevel(logging.DEBUG)
	print(get_tsm_data("eu"))