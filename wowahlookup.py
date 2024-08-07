CONNECTED_REALM_IDS = {
	1084: "Tarren Mill",
	1303: "Aggra",
	1096: "Defias"
}

MAX_ITEM_NAME_LENGTH = 25
RATIO_NOTIF_THRESHOLD = .1
REGION = "eu" # eu/us
ITEM_LIST = "items.txt"
TSM_DATA_EXPIRE_TIME = 86400 * 2
RAIDBOTS_BONUSES_DATA_EXPIRE_TIME = 86400 * 14
TIME_FIRST_CHECK_SINCE_LAST_MODIFIED = 60*55

'''
required/tsm_credentials.txt should contain only the tsm api key
'''

'''
TODO
fix inconsistencies with local saves for tsm/raidbots/slugs
rewrite in the image of raidbots one
also make is so if you cant download and there is an old local one, use it anyway
'''

from datetime import datetime
import grequests
import os
import sys
import traceback
import argparse
import logging
from time import perf_counter, time, sleep
import requests
import json
from win10toast import ToastNotifier
from dataclasses import dataclass
from blizzard_auth import get_blizzard_header
from urllib.parse import quote as urllib_quote
from tsm_data import get_tsm_data

APP_NAME = "wowahlookup"
DESCRIPTION = "Looks up prices of specific items from chosen AHs"
VERSION = "1.10"
WORKING_DIR = r"C:"
LOG_FILE = f'{APP_NAME}v{VERSION}log.txt'
FILE_DIR = __file__.rsplit("\\", 1)[0] + "\\"

'''
v1.2:
added auto mode and emailer for notifications
v1.3
added connection error catching on most requests
full traceback written on uncaught exception
v1.4
now writes the last email to disk and doesnt email if it is repeated
v1.5
reversed the order in which items are printed (cheapest at the bottom) and now
also prints the headers at the bottom
grouped traceback logs into the same dir
added MAX_ITEM_NAME_LENGTH and replacing Diff Strings with shorter names
now use dataclasses because unnecessary
v1.6
added l cmd to create a table of undermine journal links
separated get_blizzard_header into its own module
realm slugs are now a thing for linking to underminejournal
v1.7
removed l cmd
links are now hyperlinked on the names
required files should be on /required/
saved local files are on /local/ and can be safely deleted
logs are saved on /log/ and log/tracebacks/
v1.8
split downloading and parsing ah data into separate functions
uses grequests to download all AH data at the same time
v1.9
fixed urls to use undermine.exchange instead
added TSM_DATA_EXPIRE_TIME as a global at the start of the file
v1.10
item bonuses data is now downloaded from raidbots
v1.11
split getting regional tsm data to a separate file
auto mode now uses the If-Modified-Since header and tries for updates more often
'''

BLIZZARD_HOST = "https://eu.api.blizzard.com/"
RAIDBOTS_BONUSES_DATA_HOST = "https://www.raidbots.com/static/data/live/bonuses.json"

@dataclass
class Item:
	id: str
	source: str
	name: str
	diff: str

'''
example item in sorted_items as printed by pprint:
{'auction': {'buyout': 25006300,
              'id': 851674575,
              'item': {'bonus_lists': [6654, 1695],
                       'id': 14091,
                       'modifiers': [{'type': 9, 'value': 30},
                                     {'type': 28, 'value': 3}]},
              'quantity': 1,
              'time_left': 'LONG'},
  'item': Item(id='14091',
               source='Classic World',
               name='Beaded Robe',
               diff='NM'),
  'market_value': 316603581,
  'ratio': 0.07898299798447321,
  'realm': 1084},
'''

def get_bonuses():
	bonuses = 0
	try: # checking for local data
		logging.debug(f"Reading local/bonuses.json")
		with open(FILE_DIR + "local/bonuses.json") as f:
			bonuses = json.load(f)
			if os.path.getmtime(FILE_DIR + "local/bonuses.json") + RAIDBOTS_BONUSES_DATA_EXPIRE_TIME > time():
				logging.debug("Local item bonuses data still fresh, reusing")
				return bonuses
			logging.info("Local item bonuses data is too old, redownloading")
	except FileNotFoundError:
		logging.debug("No local item bonuses data found")

	try: # downloading new data
		logging.info("Downloading item bonuses data from Raidbots")
		resp = requests.get(RAIDBOTS_BONUSES_DATA_HOST)
	except ConnectionError as e:
		logging.error("Connection error when attempting to download raidbots bonuses data, check your internet connection")
		if bonuses:
			logging.info("Using possibly outdated local raidbots data")
			return bonuses
		return e
	if resp.status_code != 200:
		logging.error("Failed to get Raidbots data", resp, resp.reason)
		if bonuses:
			logging.info("Using possibly outdated local raidbots data")
			return bonuses
		return e
	
	bonuses = json.loads(resp.text)

	with open(FILE_DIR + "local/bonuses.json", "w") as f:
			json.dump(bonuses, f, indent="\t")
			logging.debug("Saved item bonuses data from Raidbots to local/bonuses.json")
	return bonuses

def parse_items():
	logging.debug(f"Reading {ITEM_LIST}")
	with open(FILE_DIR + ITEM_LIST) as input:
		items = [[i.strip() for i in l.strip().split(",")] for l in input.readlines() if l[0] != "#" and l[0] != "\n"]
	out = {}
	for item in items:
		item.append("Normal") # append default value for diff
		try:
			id, source, name, diff, *_ = item
		except ValueError as e:
			logging.error(f"ValueError while unpacking the following entry: {item}")
			exit()
		if id not in out:
			out[id] = [Item(id, source, name, diff)]
		else:
			out[id].append(Item(id, source, name, diff))
	logging.debug("Parsed item input")
	return out

# might delete later
def dl_ah_data():
	try:
		bearer, params = get_blizzard_header(REGION)
	except requests.exceptions.ConnectionError as e:
		logging.error("Connection error when attempting to get blizzard auths, check your internet connection")
		return e

	ah_data = {}

	for ah, ah_name in CONNECTED_REALM_IDS.items():
		logging.debug(f"Requesting {ah_name} AH data")
		try:
			x = requests.get(
				f"{BLIZZARD_HOST}data/wow/connected-realm/{ah}/auctions", 
				headers=bearer, params=params)
		except ConnectionError as e:
			logging.error("Connection error when attempting to download AH data, check your internet connection")
			return e
		if x.status_code != 200:
			logging.error("Failed to get AH data")
			logging.error(x, x.reason)
			return
		ah_data[ah] = json.loads(x.text)["auctions"]
		logging.info(f"There are {len(ah_data[ah])} items for auction in {ah_name}")
	
	return ah_data

def dl_ah_data_grequests(if_modified_since=False):
	try:
		bearer, params = get_blizzard_header(REGION)
	except requests.exceptions.ConnectionError as e:
		logging.error("Connection error when attempting to get blizzard auths, check your internet connection")
		return e
	
	if if_modified_since:
		bearer["If-Modified-Since"] = if_modified_since

	error_flag = False
	def e_handler(request, e):
		nonlocal error_flag
		if type(e) == requests.exceptions.ConnectionError and not error_flag:
			logging.error("Connection error when attempting to download AH data, check your internet connection")
			error_flag = True
		if type(e) != requests.exceptions.ConnectionError:
			logging.error(f"Request {type(e)=}failed for unchecked reason: {e}")
			error_flag = True

	rs = (
		grequests.get(
			f"{BLIZZARD_HOST}data/wow/connected-realm/{ah}/auctions",
			headers=bearer,
			params=params)
		for ah in CONNECTED_REALM_IDS.keys())
	
	print("Requesting AH data from blizzard")
	ah_data = {}
	last_modified = {}
	for resp, (ah, ah_name) in zip(grequests.map(rs, exception_handler=e_handler), CONNECTED_REALM_IDS.items()):
		if error_flag:
			return -1
		
		if resp.status_code == 200:
			last_modified[ah] = resp.headers["last-modified"]
			ah_data[ah] = json.loads(resp.text)["auctions"]
			logging.info(f"There are {len(ah_data[ah])} items for auction in {ah_name}")
		elif resp.status_code == 304:
			return 304
		else:
			logging.error(f"Unhandled grequest response: {resp.status_code=}")
			return -1
		

	with open(FILE_DIR + "local/last_modified.json", "w") as f:
		json.dump(last_modified, f, indent="\t")
	logging.debug(f"Wrote to local/last_modified.json")
			
	return ah_data

def parse_ahs(item_list, ah_data, market_values=False):
	logging.debug("Parsing AH data")
	bonuses = get_bonuses()

	out = {}
	for key in item_list:
		out[key] = []

	for ah, auctions in ah_data.items():
		for auction in auctions:
			if (id := str(auction['item']['id'])) in item_list:
				no_diff_id = True
				if auction["item"].get("bonus_lists"):
					for bonus_id in auction["item"]["bonus_lists"]:
						if not bonuses.get(str(bonus_id)):
							# logging.warning(f"{bonus_id} is not part of RaidBots' list of ids, it was found on this item {auction}")
							continue
						for item in item_list[id]:
							if (_t := bonuses[str(bonus_id)].get("tag", False)):
								no_diff_id = False
								if _t == item.diff:
									out[id].append({
										"item": item,
										"auction": auction,
										"realm": ah,
										"market_value": market_values[id] if market_values else 0,
									})
					if no_diff_id:
						for item in item_list[id]:
							if item.diff == "Normal":
								out[id].append({
									"item": item,
									"auction": auction,
									"realm": ah,
									"market_value": market_values[id] if market_values else 0,
								})
				else:
					out[id].append({
						"item": item_list[id][0],
						"auction": auction,
						"realm": ah,
						"market_value": market_values[id] if market_values else 0,
					})
			elif id == "82800": # Pet Cages
				if (pet_id := f"P{auction['item']['pet_species_id']}") in item_list:
					out[pet_id].append({
						"item": item_list[pet_id][0],
						"auction": auction,
						"realm": ah,
						"market_value": market_values[pet_id] if market_values else 0,
					})
		logging.debug(f"Parsed {CONNECTED_REALM_IDS[ah]} items")
	return out

def get_cheapest(items):
	cheapest = {}
	for id_group in items.values():
		for item in id_group:
			identifier = f'{item["item"].id}:{item["item"].diff}'
			if identifier not in cheapest:
				cheapest[identifier] = item
			else:
				if item["auction"].get("buyout", 10e11) < cheapest[identifier]["auction"]["buyout"]:
					cheapest[identifier]["auction"]["buyout"] = item["auction"].get("buyout", 10e11)
					cheapest[identifier]["realm"] = item["realm"]
				if item["auction"].get("bid", float("inf")) < cheapest[identifier]["auction"].get("bid", float("inf")):
					cheapest[identifier]["auction"]["bid"] = item["auction"].get("bid")
					if cheapest[identifier]["realm"] != item["realm"]:
						cheapest[identifier]["bid_on_diff_realm"] = item["realm"]
	return cheapest

def populate_ratios(items):
	for item in items.values():
		ratio_against = min(item["auction"].get("bid", float("inf")), item["auction"]["buyout"])
		item["ratio"] = ratio_against/item["market_value"] if item["market_value"] else 0

def pad_value(val, pad):
	return str(val) + " "*(pad - len(str(val)))

def print_items_pretty(sorted_items):
	logging.debug("Pretty printing items")

	columns = {
		"id": 2,
		"name": 4,
		"diff": 3,
		"source": 6,
		"bid": 3,
		"buyout": 6,
		"realm": 5,
		"marketV": 7,
		"ratio": 5
	}

	DIFF_STRINGS_REPLACEMENTS = {
		"Raid Finder": "LFR",
		"Normal": "NM",
		"Heroic": "HC",
		"Mythic": "M",
		"Fated Raid Finder": "FLFR",
		"Fated Normal": "FNM",
		"Fated Heroic": "FHC",
		"Fated Mythic": "FM",
	}

	for item in sorted_items:
		if (item["auction"].get("bid", 0) > item["auction"]["buyout"]):
			item["auction"].pop("bid")
			if item.get("bid_on_diff_realm", False):
				item.pop("bid_on_diff_realm")
		for column in columns.keys():
			match column:
				case "id":
					if len(str(item["item"].id)) > columns[column]:
						columns[column] = len(str(item["item"].id))
				case "name":
					item["item"].name = item["item"].name[:MAX_ITEM_NAME_LENGTH]
					if len(item["item"].name) > columns[column]:
						columns[column] = len(item["item"].name)
				case "diff":
					if item["item"].diff in DIFF_STRINGS_REPLACEMENTS:
						item["item"].diff = DIFF_STRINGS_REPLACEMENTS[item["item"].diff]
					if len(item["item"].diff) > columns[column]:
						columns[column] = len(item["item"].diff)
				case "source":
					if len(item["item"].source) > columns[column]:
						columns[column] = len(item["item"].source)
				case "bid":
					bid = len(str(round(item["auction"]
						.get("bid", -10000000)/10000000))) + 1
					if item.get("bid_on_diff_realm", False): bid += 1
					if bid > columns[column]:
						columns[column] = bid
				case "buyout":
					buyout = len(str(round(
						item["auction"]["buyout"]/10000000))) + 1
					if buyout > columns[column]:
						columns[column] = buyout
				# trimming realm names to fit 5 digits so skipping this
				# case "realm":
				# 	if len(CONNECTED_REALM_IDS[item["realm"]]) > columns[column]:
				# 		columns[column] = len(CONNECTED_REALM_IDS[item["realm"]])
				case "marketV":
					mv = len(str(round(
						item["market_value"]/10000000))) + 1
					if mv > columns[column]:
						columns[column] = mv

	table_headers = (
		f'| {pad_value("ID", columns["id"])}'
		f' | {pad_value("Name", columns["name"])}'
		f' | {pad_value("Dif", columns["diff"])}'
		f' | {pad_value("Source", columns["source"])}'
		f' | {pad_value("Bid", columns["bid"])}'
		f' | {pad_value("Buyout", columns["buyout"])}'
		f' | {pad_value("Realm", columns["realm"])}'
		f' | {pad_value("Ratio", columns["ratio"])}'
		f' | {pad_value("MarketV", columns["marketV"])}'
		f' |' 
		)

	sorted_items = populate_realm_slugs(sorted_items)
	for item in sorted_items:
		# if item["item"].id[0] == "P": # a pet
		# 	f"https://theunderminejournal.com/#{REGION}/{item['realm_slug']}/battlepet/{item['item'].id[1:]}"
		# else:
		item["link"] = f"https://undermine.exchange/#{REGION}-{item['realm_slug']}/search/opt=transmog-mode/{urllib_quote(item['item'].name)}"
		item["hyperlink_string"] = f"\033]8;;{item['link']}\033\\{item['item'].name}\033]8;;\033\\"


	print(table_headers)
	longest_line_length = len(table_headers)
	print("-"*longest_line_length)
	
	for item in sorted_items[::-1]:
		id = pad_value(item["item"].id, columns["id"])
		# name = pad_value(item["item"].name, columns["name"])
		name = item["hyperlink_string"] + " "*(columns["name"] - len(item["item"].name))
		diff = pad_value(item["item"].diff, columns["diff"])
		source = pad_value(item["item"].source, columns["source"])
		_bid = str(round(item["auction"].get("bid", -10000000)/10000000)) + "k"
		if item.get("bid_on_diff_realm", False): _bid += "*"
		bid = pad_value(_bid if _bid != "-1k" else "-", columns["bid"])
		buyout = pad_value(str(round(item["auction"]["buyout"]/10000000)) + "k", columns["buyout"])
		realm = CONNECTED_REALM_IDS[item["realm"]][:columns["ratio"]]
		ratio = pad_value(str(round(item["ratio"], 2)) if item["ratio"] < 1 else ">1", columns["ratio"])
		marketV = pad_value(str(round(item["market_value"]/10000000)) + "k", columns["marketV"])
		line = f'| {id} | {name} | {diff} | {source} | {bid} | {buyout} | {realm} | {ratio} | {marketV} |'
		if r := item.get("bid_on_diff_realm", False): line += f" *{CONNECTED_REALM_IDS[r]}"
		print(line)
		if len(line) > longest_line_length: longest_line_length = len(line)
	
	print("-"*len(table_headers))
	print(table_headers)
	logging.debug("Finished printing items")

def send_windows_toast(msg):
	toaster = ToastNotifier()
	toaster.show_toast("WoWAHLookUp", msg, duration=10)

def check_low_ratio(sorted_items):
	logging.debug("Checking if there are any deals")
	msg = ""
	for item in sorted_items:
		if item["ratio"] > RATIO_NOTIF_THRESHOLD:
			if msg != "":
				print(msg)
			else:
				print("No good prices found")
				return
			
			try:
				logging.debug("Reading local/last_email.txt")
				with open(FILE_DIR + "local/last_email.txt") as f:
					if f.read() == msg:
						logging.info("Message is the same as the last iteration, not sending")
						return
			except FileNotFoundError:
				pass
			
			with open(FILE_DIR + "local/last_email.txt", "w") as f:
				logging.info("Wrote message to local/last_email.txt")
				f.write(msg)
				if msg != "":
					logging.info("Emailing...")
					sys.path.append(FILE_DIR + "..\\emailer")
					import emailer
					emailer.email_notif("WoWAHLookUp: Found item", msg)
					# sendWindowsToast(msg)
			return

		if realm := item.get("bid_on_diff_realm", False):
			_price = item["auction"].get("bid", float("inf"))
		else:
			_price = item["auction"]["buyout"]
			realm = item["realm"]
		
		price = str(round(_price/10000000)) + "k"
		msg += f'Found {item["item"].name} ({item["item"].source}) in {CONNECTED_REALM_IDS[realm]} for {price} ({round(item["ratio"]*100)}%)\n'

def populate_realm_slugs(item_list):
	header, params = get_blizzard_header(REGION)
	slugs = {}

	# check local slugs
	try:
		logging.debug("Reading local/realm_slugs.json")
		with open(FILE_DIR + "local/realm_slugs.json") as f:
			slugs = json.load(f)
			slugs = {int(k):v for k,v in slugs.items()}
	except FileNotFoundError:
		logging.debug("No realm slugs saved")
	except ValueError:
		slugs = {}
		logging.error("ValueError when reading realm_slugs.json, redownloading")

	# check if any are missing and download them
	missing = 0
	for realm_id in CONNECTED_REALM_IDS.keys():
		if realm_id in slugs:
			continue # skip if already exists

		missing += 1
		resp = requests.get(
			f"{BLIZZARD_HOST}data/wow/connected-realm/{realm_id}",
			headers=header,
			params=params
		)
		slugs[realm_id] = json.loads(resp.text)["realms"][0]["slug"]

	# only save if there are updates
	if missing:
		logging.debug("Downloaded missing slugs")
		with open(FILE_DIR + "local/realm_slugs.json", "w") as f:
			json.dump(slugs, f, indent="\t")
			logging.debug("Saved realm slugs to local/realm_slugs.json")

	for item in item_list:
		item["realm_slug"] = slugs[item["realm"]]
	
	logging.debug("Populated items with realm slugs")
	return item_list

# might delete later
def print_item_links(sorted_items):
	sorted_items = populate_realm_slugs(sorted_items)

	columns = {
		"name": 4,
		"link": 4,
	}

	# generate links
	for item in sorted_items:
		if item["item"].id[0] == "P": # a pet
			item["link"] = f"https://theunderminejournal.com/#{REGION}/{item['realm_slug']}/battlepet/{item['item'].id[1:]}"
		else:
			item["link"] = f"https://theunderminejournal.com/#{REGION}/{item['realm_slug']}/item/{item['item'].id}"

	for item in sorted_items:
		for column in columns.keys():
			match column:
				case "name":
					item["item"].name = item["item"].name[:MAX_ITEM_NAME_LENGTH]
					if len(item["item"].name) > columns[column]:
						columns[column] = len(item["item"].name)
				case "link":
					if len(item["link"]) > columns[column]:
						columns[column] = len(item["link"])

	table_headers = (
		f'| {pad_value("Name", columns["name"])}'
		f' | {pad_value("Undermine Journal Link", columns["link"])}'
		f' |'
	)

	print(table_headers)
	longest_line_length = len(table_headers)
	print("-"*longest_line_length)

	for item in sorted_items[::-1]:
		name = pad_value(item["item"].name, columns["name"])
		link = pad_value(item["link"], columns["link"])
		line = f'| {name} | {link} |'
		print(line)
	
	print("-"*len(table_headers))
	print(table_headers)

def main(args):
	os.makedirs(FILE_DIR+"local", exist_ok=True)

	tsm_data = get_tsm_data(REGION, TSM_DATA_EXPIRE_TIME)
	items = parse_items()
	ah_data = dl_ah_data_grequests()
	if type(ah_data) != dict:
		logging.error("No AH data available, exiting")
		return -1

	relevant_items = parse_ahs(items, ah_data, market_values=tsm_data)
	if type(relevant_items) != dict:
		logging.error(f"Error when parsing AH data: {relevant_items}")
		return -1
	
	cheapest = get_cheapest(relevant_items)
	populate_ratios(cheapest)

	# sorting methods
	bybuyout = lambda item: item["auction"]["buyout"]
	byminbidout = lambda item: min(item["auction"].get("bid", float("inf")), item["auction"]["buyout"])
	byratio = lambda item: item["ratio"]
	byname = lambda item: item["item"].name
	def byid(item):
		id_str = item["item"].id
		if id_str[0] == "P":
			return int(id_str[1:])*-1
		return int(id_str)

	sort_cmds = {
		"r": {"f": byratio, "help": "sort by ratio (default)"},
		"b": {"f": bybuyout, "help": "sort by buyout"},
		"m": {"f": byminbidout, "help": "sort by bid then buyout"},
		"n": {"f": byname, "help": "name"},
		"i": {"f": byid, "help": "id"},
	}

	sorted_items = sorted(cheapest.values(), key=byratio)

	if not args.auto:
		print_items_pretty(sorted_items)
		while True:
			try:
				cmd, *args = input("Enter key:").strip().lower().split()
			except KeyboardInterrupt:
				return
			except ValueError:
				cmd = ""
			if cmd in sort_cmds:
				print_items_pretty(sorted(cheapest.values(), key=sort_cmds[cmd]["f"]))
				continue
			match cmd:
				case "c":
					return
				case _:
					for k, v in sort_cmds.items():
						print(f"{k} - {v['help']}")
					print(
						"c - exit",
						sep="\n"
					)
	else:
		print_items_pretty(sorted_items[:5])
		check_low_ratio(sorted_items)

		while True:
			# check every 1 minute after 50m since last update
			last_modified_unix = os.path.getmtime(FILE_DIR + "local/last_modified.json")
			if last_modified_unix + TIME_FIRST_CHECK_SINCE_LAST_MODIFIED > time():
				time_to_wait = last_modified_unix + TIME_FIRST_CHECK_SINCE_LAST_MODIFIED - time()
				dt = datetime.fromtimestamp(last_modified_unix + TIME_FIRST_CHECK_SINCE_LAST_MODIFIED)
				logging.info(f"AH data is recent enough sleeping until {dt.strftime("%H:%M")}")
				sleep(time_to_wait)
			
			logging.debug(f"Reading local/last_modified.json")
			with open(FILE_DIR + "local/last_modified.json") as f:
				d = json.load(f)
				last_modified = d[next(iter(d))]

			logging.debug("Checking for updated AH data")
			while True:
				ah_data = dl_ah_data_grequests(last_modified)
				if ah_data == 304:
					logging.info("AH data not updated yet, checking again in 60s")
					sleep(60)
				elif type(ah_data) != dict:
					logging.error("No AH data available, trying again in 5 minutes")
					sleep(300)
				else:
					relevant_items = parse_ahs(items, ah_data, market_values=tsm_data)
					if type(relevant_items) != dict:
						logging.error(f"Error when parsing AH data: {relevant_items}")
						return -1
					
					cheapest = get_cheapest(relevant_items)
					populate_ratios(cheapest)
					sorted_items = sorted(cheapest.values(), key=byratio)
					print_items_pretty(sorted_items[:5])
					check_low_ratio(sorted_items)
					break


if __name__ == '__main__':
	t0 = perf_counter()

	# parse input
	parser = argparse.ArgumentParser(description=DESCRIPTION)
	parser.add_argument("-log", type=str, default="INFO", help="set log level for console output, WARNING/INFO/DEBUG")
	parser.add_argument("-logfile", type=str, default="0", help="sets file logging level, 0/CRITICAL/ERROR/WARNING/INFO/DEBUG, set to 0 to disable")
	parser.add_argument("-auto", action="store_true", default=False, help="turns off printing and prompting for input")

	args = parser.parse_args()

	log_format=logging.Formatter(f'%(asctime)s {APP_NAME} v{VERSION} %(levelname)s:%(name)s:%(funcName)s %(message)s')
	# setting up logger to info on terminal and debug on file
	stream_handler = logging.StreamHandler(sys.stdout)
	stream_handler.setLevel(getattr(logging, args.log.upper()))
	# stream_handler.setFormatter(log_format)
	logging.getLogger().addHandler(stream_handler)

	if args.logfile != "0":
		file_handler = logging.FileHandler(filename=FILE_DIR+"log/"+LOG_FILE, mode="a")
		file_handler.setLevel(getattr(logging, args.logfile.upper()))
		file_handler.setFormatter(log_format)
		logging.getLogger().addHandler(file_handler)
		logging.getLogger().setLevel(getattr(logging, args.logfile.upper()))

		def uncaught_exception_hook(exc_type, exc_value, exc_traceback):
			traceback_file_path = FILE_DIR+f"log/traceback/TRACEBACK{time()}"+LOG_FILE
			os.makedirs(FILE_DIR+"log/errorlog", exist_ok=True)
			with open(traceback_file_path, mode="a") as traceback_file:
				traceback_file.write(f"Uncaught exception, type: {exc_type.__name__}")
				traceback.print_exception(exc_value, file=traceback_file)
				traceback.print_tb(exc_traceback, file=traceback_file)
			logging.error(f"Uncaught exception, type: {exc_type.__name__}, full traceback written to {traceback_file_path}\n")
				
		sys.excepthook = uncaught_exception_hook
	else:
		logging.getLogger().setLevel(getattr(logging, args.log.upper()))

	logging.debug(f"Started with arguments: {sys.argv}")

	main(args)

	logging.info(f"Exited. Ran for {round(perf_counter() - t0, 3)}s\n")