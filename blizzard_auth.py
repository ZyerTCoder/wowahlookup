BLIZZARD_AUTH = "https://oauth.battle.net/token"
CREDENTIALS = "required/blizzard_credentials.txt"
'''credetials should be pasted in the file named above in this order:
blizzard client id
blizzard secret id
'''

import logging
import os
import json
import requests
from time import time

FILE_DIR = __file__.rsplit("\\", 1)[0] + "\\"

auth = 0

def get_blizzard_header(region):
	logging.debug("Getting blizzard bearer token")
	global auth
	params = {
		"namespace": f"dynamic-{region}",
		"locale": "en_US",
	}

	# check local
	if auth != 0:
		if auth.get("expires_on", 0) > time():
			return {"Authorization": "Bearer " + auth["access_token"]}, params

	# get from saved file
	try:
		with open(FILE_DIR+"local/auth.json") as f:
			logging.debug(f"Reading local/auth.json")
			last_auth = json.load(f)
			if last_auth.get("expires_on", 0) > time():
				logging.debug("Saved auth is still valid")
				auth = last_auth
				return {"Authorization": "Bearer " + last_auth["access_token"]}, params
			else:
				logging.debug("Saved auth has expired")
	except FileNotFoundError:
		if not os.path.isdir(FILE_DIR+"local"):
			os.makedirs(FILE_DIR+"local")
			logging.debug("Made "+FILE_DIR+"local")

	# ask blizzard
	logging.debug(f"Reading {CREDENTIALS}")
	with open(FILE_DIR + CREDENTIALS, "r") as c:
		lines = [l.strip() for l in c.readlines()]
		client_id = lines[0]
		client_secret = lines[1]

	x = requests.post(
		BLIZZARD_AUTH, 
		data={'grant_type': 'client_credentials'},
		auth=(client_id, client_secret))
	resp = json.loads(x.text)
	auth = resp
	logging.debug("Blizzard bearer token obtained")
	
	with open(FILE_DIR + "local/auth.json", "w") as f:
		resp["expires_on"] = time() + resp["expires_in"]
		f.write(json.dumps(resp, indent="\t"))
		logging.debug("Wrote token to local/auth.json")
	return {"Authorization": "Bearer " + resp["access_token"]}, params