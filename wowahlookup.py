CONNECTED_REALM_IDS = {
	1084: "Tarren Mill",
	1303: "Aggra",
	1096: "Defias"
}

RATIO_NOTIF_THRESHOLD = .1
REGION = "eu" # eu/us
ITEM_LIST = "items.txt"
BONUSES_LIST_JSON = "bonuses.json"
CREDENTIALS = "credentials"
'''credetials should be pasted in the file named above in this order:
blizzard client id
blizzard secret id
tsm api key
'''

'''
TODO
add extra options on prompt after the initial print:
	links to undermine journal pages
	modular columns in the table for better links (just id/name/link)
'''

import sys
import traceback
import argparse
import logging
from time import perf_counter, time
import requests
import json
from win10toast import ToastNotifier

APP_NAME = "wowahlookup"
DESCRIPTION = "Looks up prices of specific items from chosen AHs"
VERSION = "1.4.1"
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
'''

BLIZZARD_AUTH = "https://oauth.battle.net/token"
BLIZZARD_HOST = "https://eu.api.blizzard.com/"
TSM_AUTH = "https://auth.tradeskillmaster.com/oauth2/token"
TSM_REALM = "https://realm-api.tradeskillmaster.com/"
TSM_PRICE = "https://pricing-api.tradeskillmaster.com/"
LOCAL_TSM_FILE = "tsm_data.json"

class Item:
	def __init__(self, id, source, name, diff="Normal"):
		self.id = id
		self.source = source
		self.name = name
		self.diff = diff

def get_blizzard_header():
	logging.debug(f"Reading {CREDENTIALS}")
	with open(FILE_DIR + CREDENTIALS, "r") as c:
		lines = [l.strip() for l in c.readlines()]
		client_id = lines[0]
		client_secret = lines[1]
	x = requests.post(
		BLIZZARD_AUTH, 
		data={'grant_type': 'client_credentials'},
		auth=(client_id, client_secret))
	access_token = json.loads(x.text)["access_token"]
	logging.debug("Blizzard bearer token obtained")
	return {"Authorization": "Bearer " + access_token}

def get_tsm_header():
	logging.debug(f"Reading {CREDENTIALS}")
	with open(FILE_DIR + CREDENTIALS, "r") as c:
		lines = [l.strip() for l in c.readlines()]
		stuff = {
			"client_id": "c260f00d-1071-409a-992f-dda2e5498536",
			"grant_type": "api_token",
			"scope": "app:realm-api app:pricing-api",
			"token": lines[2]
		}
	x = requests.post(
		TSM_AUTH, 
		data=stuff)
	logging.debug("TSM bearer token obtained")
	r = json.loads(x.text)
	if not r.get("access_token", False):
		raise KeyError("Error getting access token from TSM")

	return {"Authorization": "Bearer " + r["access_token"]}

def get_bonuses():
	logging.debug(f"Reading {BONUSES_LIST_JSON}")
	with open(FILE_DIR + BONUSES_LIST_JSON, "r") as f:
		return json.loads(f.read())

def parse_items():
	logging.debug(f"Reading {ITEM_LIST}")
	with open(FILE_DIR + ITEM_LIST, "r") as input:
		items = [[i.strip() for i in l.strip().split(",")] for l in input.readlines() if l[0] != "#" and l[0] != "\n"]
	out = {}
	for item in items:
		item.append("Normal") # append default value for diff
		id, source, name, diff, *_ = item
		if id not in out:
			out[id] = [Item(id, source, name, diff)]
		else:
			out[id].append(Item(id, source, name, diff))
	logging.debug("Parsed item input")
	return out

def parse_ahs(item_list, market_values):
	try:
		bearer = get_blizzard_header()
	except requests.exceptions.ConnectionError as e:
		logging.error("Connection error when attempting to get blizzard auths, check your internet connection")
		return e
	
	bonuses = get_bonuses()
	params = {
		"namespace": f"dynamic-{REGION}",
		"locale": "en_US",
	}

	out = {}
	for key in item_list:
		out[key] = []

	for ah, ah_name in CONNECTED_REALM_IDS.items():
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

		auctions = json.loads(x.text)["auctions"]
		logging.info(f"There are {len(auctions)} items for auction in {ah_name}")
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
										"market_value": market_values[id],
									})
					if no_diff_id:
						for item in item_list[id]:
							if item.diff == "Normal":
								out[id].append({
									"item": item,
									"auction": auction,
									"realm": ah,
									"market_value": market_values[id],
								})
				else:
					out[id].append({"item": item_list[id][0], "auction": auction, "realm": ah, "market_value": market_values[id]})
			elif id == "82800": # Pet Cages
				if (pet_id := f"P{auction['item']['pet_species_id']}") in item_list:
					out[pet_id].append({
						"item": item_list[pet_id][0],
						"auction": auction,
						"realm": ah,
						"market_value": market_values[pet_id],
					})
		logging.debug(f"Parsed {ah_name} items")
	return out

def parse_tsm_data():
	match REGION:
		case "na": r = 1
		case "eu": r = 2
	
	try:
		logging.info("Downloading TSM AH data")
		bearer = get_tsm_header()
		tsm_resp = requests.get(f"{TSM_PRICE}region/{r}", headers=bearer)
	except requests.exceptions.ConnectionError as e:
		logging.error("Connection error when attempting to get tsm data, check your internet connection")
		return e
	if tsm_resp.status_code != 200:
		logging.error("Failted to get TSM data")
		logging.error(tsm_resp, tsm_resp.reason)
		return
	items = json.loads(tsm_resp.text)

	logging.debug(f"Parsing TSM data for {REGION.upper()}")
	tsm_data = {"date": time()}
	for entry in items:
		if entry["itemId"]:
			tsm_data[str(entry["itemId"])] = entry["marketValue"]
		elif entry["petSpeciesId"]:
			tsm_data["P" + str(entry["petSpeciesId"])] = entry["marketValue"]
	logging.info(f"Parsed TSM data for {REGION.upper()}, {len(tsm_data)-1} entries")

	with open(FILE_DIR + LOCAL_TSM_FILE, "w") as f:
		logging.debug(f"Writing TSM data to {LOCAL_TSM_FILE}")
		json.dump(tsm_data, f, indent="\t")
	return tsm_data

def get_cheapest(items):
	cheapest = {}
	for id_group in items.values():
		for item in id_group:
			identifier = f'{item["item"].id}:{item["item"].diff}'
			if identifier not in cheapest:
				cheapest[identifier] = item
			else:
				if item["auction"]["buyout"] < cheapest[identifier]["auction"]["buyout"]:
					cheapest[identifier]["auction"]["buyout"] = item["auction"]["buyout"]
					cheapest[identifier]["realm"] = item["realm"]
				if  item["auction"].get("bid", float("inf")) < cheapest[identifier]["auction"].get("bid", float("inf")):
					cheapest[identifier]["auction"]["bid"] = item["auction"].get("bid")
					if cheapest[identifier]["realm"] != item["realm"]:
						cheapest[identifier]["bid_on_diff_realm"] = item["realm"]
	return cheapest

def populate_ratios(items):
	for item in items.values():
		ratio_against = min(item["auction"].get("bid", float("inf")), item["auction"]["buyout"])
		item["ratio"] = ratio_against/item["market_value"]

def print_items_pretty(sorted_items):
	logging.debug("Pretty printing items")

	columns = {
		"id": 2,
		"name": 4,
		"diff": 4,
		"source": 6,
		"bid": 3,
		"buyout": 6,
		"realm": 5,
		"marketV": 7,
		"ratio": 5
	}

	for item in sorted_items:
		if (item["auction"].get("bid")
			and item["auction"].get("bid") > item["auction"]["buyout"]):
			item["auction"].pop("bid")
			if item.get("bid_on_diff_realm", False):
				item.pop("bid_on_diff_realm")
		for column in columns.keys():
			match column:
				case "id":
					if len(str(item["item"].id)) > columns[column]:
						columns[column] = len(str(item["item"].id))
				case "name":
					if len(item["item"].name) > columns[column]:
						columns[column] = len(item["item"].name)
				case "diff":
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
				# case "realm":
				# 	if len(CONNECTED_REALM_IDS[item["realm"]]) > columns[column]:
				# 		columns[column] = len(CONNECTED_REALM_IDS[item["realm"]])
				case "marketV":
					mv = len(str(round(
						item["market_value"]/10000000))) + 1
					if mv > columns[column]:
						columns[column] = mv
	
	def pad_value(val, pad):
		return str(val) + " "*(pad - len(str(val)))

	line = (
		f'| {pad_value("ID", columns["id"])}'
		f' | {pad_value("Name", columns["name"])}'
		f' | {pad_value("Diff", columns["diff"])}'
		f' | {pad_value("Source", columns["source"])}'
		f' | {pad_value("Bid", columns["bid"])}'
		f' | {pad_value("Buyout", columns["buyout"])}'
		f' | {pad_value("Realm", columns["realm"])}'
		f' | {pad_value("Ratio", columns["ratio"])}'
		f' | {pad_value("MarketV", columns["marketV"])}'
		f' |' 
		)
	print(line)
	longest_line = len(line)
	print("-"*len(line))
	for item in sorted_items:
		id = pad_value(item["item"].id, columns["id"])
		name = pad_value(item["item"].name, columns["name"])
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
		if len(line) > longest_line: longest_line = len(line)

def sendWindowsToast(msg):
	toaster = ToastNotifier()
	toaster.show_toast("WoWAHLookUp", msg, duration=10)

def check_low_ratio(sorted_items):
	msg = ""
	for item in sorted_items:
		if item["ratio"] > RATIO_NOTIF_THRESHOLD:
			print(msg)
			try:
				with open(FILE_DIR + "lastemail.txt", "r") as f:
					if f.read() == msg:
						logging.info("Message is the same as the last iteration, not sending.")
						return
			except FileNotFoundError:
				pass

			with open(FILE_DIR + "lastemail.txt", "w") as f:
				logging.info("Wrote message to disk")
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
		

def main(args):
	try:
		with open(FILE_DIR + LOCAL_TSM_FILE) as f:
			tsm_data = json.load(f)
			if tsm_data["date"] + 86400 < time():
				logging.info("Local TSM data is too old, renewing")
				raise FileNotFoundError
			logging.info("Local TSM data still fresh, reusing")
	except FileNotFoundError:
		tsm_data = parse_tsm_data()

	items = parse_items()
	relevant_items = parse_ahs(items, tsm_data)
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
	byid = lambda item: item["item"].id

	sorted_items = sorted(cheapest.values(), key=byratio)

	if not args.auto:
		print_items_pretty(sorted_items)
		while True:
			try:
				i = input("Enter key:").strip().lower()
			except KeyboardInterrupt:
				return
			match i:
				case "l":
					pass
				case "r":
					print_items_pretty(sorted(cheapest.values(), key=byratio))
				case "b":
					print_items_pretty(sorted(cheapest.values(), key=bybuyout))
				case "m":
					print_items_pretty(sorted(cheapest.values(), key=byminbidout))
				case "n":
					print_items_pretty(sorted(cheapest.values(), key=byname))
				case "i":
					print_items_pretty(sorted(cheapest.values(), key=byid))
				case "c":
					break
				case _:
					print(
						"l - links to item pages",
						"r - sort by ratio (default)",
						"b - sort by buyout",
						"m - sort by bid then buyout",
						"n - name",
						"i - id",
						"c - exit",
						sep="\n"
					)
	else:
		check_low_ratio(sorted_items)

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
		file_handler = logging.FileHandler(filename=FILE_DIR+LOG_FILE, mode="a")
		file_handler.setLevel(getattr(logging, args.logfile.upper()))
		file_handler.setFormatter(log_format)
		logging.getLogger().addHandler(file_handler)
		logging.getLogger().setLevel(getattr(logging, args.logfile.upper()))

		def uncaught_exception_hook(exc_type, exc_value, exc_traceback):
			traceback_file_path = FILE_DIR+f"TRACEBACK{time()}"+LOG_FILE
			logging.error(f"Uncaught exception, type: {exc_type.__name__}, full traceback written to {traceback_file_path}\n")
			with open(traceback_file_path, mode="a") as traceback_file:
				traceback_file.write(f"Uncaught exception, type: {exc_type.__name__}")
				traceback.print_exception(exc_value, file=traceback_file)
				traceback.print_tb(exc_traceback, file=traceback_file)
				
		sys.excepthook = uncaught_exception_hook
	else:
		logging.getLogger().setLevel(getattr(logging, args.log.upper()))

	logging.debug(f"Started with arguments: {sys.argv}")

	main(args)

	logging.info(f"Exited. Ran for {round(perf_counter() - t0, 3)}s\n")