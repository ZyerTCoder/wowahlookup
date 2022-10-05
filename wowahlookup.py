import sys
import os
import argparse
import logging
import time
import requests
import json

APP_NAME = "wowahlookup"
VERSION = 1.1
WORKING_DIR = r"C:"
LOG_FILE = f'{APP_NAME}v{VERSION}log.txt'
DESCRIPTION = "Looks up prices of specific items from chosen AHs"

BONUSES_LIST_JSON = "bonuses.json"
REGION = "eu" # eu/us

connected_realm_ids = {
	1084: "Tarren Mill",
	1303: "Aggra",
	1096: "Defias"
}

AUTH_URL = "https://oauth.battle.net/token"
HOST = "https://eu.api.blizzard.com/"

class Item:
	def __init__(self, id, diff, source, name):
		self.id = id
		self.diff = diff
		self.source = source
		self.name = name

ITEMS = {
	# 76158: [
	# 	Item(76158, "Normal", "Well of Eternity", "Courtier's Slippers"),
	# 	Item(76158, "Heroic", "Well of Eternity", "Courtier's Slippers"),
	# ],
	187019: [
		Item(187019, "Normal", "Korthia", "Infiltrator's Shoulderguards"),
	],
	187097: [
		Item(187097, "Normal", "Korthia", "Construct's Shoulderplates"),
	],
	187024: [
		Item(187024, "Normal", "Korthia", "Necromancer's Mantle"),
	],
	124182: [
		Item(124182, "Heroic", "HFC", "Cord of Unhinged Malice"),
	],
	124150: [
		Item(124150, "Heroic", "HFC", "Desiccated Soulrender Slippers"),
		Item(124150, "Normal", "HFC", "Desiccated Soulrender Slippers"),
	],
	142541: [
		Item(142541, "Normal", "ToV", "Drape of the Forgotten Souls"),
		Item(142541, "Heroic", "ToV", "Drape of the Forgotten Souls"),
		Item(142541, "Mythic", "ToV", "Drape of the Forgotten Souls"),
	],
	144400: [
		Item(144400, "Raid Finder", "NH", "Feathermane Feather Cloak"),
	],
	144403: [
		Item(144403, "Raid Finder", "NH", "Fashionable Autumn Cloak"),
	],
	147517: [
		# Item(147517, "Normal", "CoTN", "Inquisitor's Battle Cowl")
	],
	152084: [
		Item(152084, "Raid Finder", "ABT", "Gloves of Abhorrent Strategies"),
		Item(152084, "Normal", "ABT", "Gloves of Abhorrent Strategies"),
		Item(152084, "Heroic", "ABT", "Gloves of Abhorrent Strategies"),
		# Item(152084, "Mythic", "ABT", "Gloves of Abhorrent Strategies"),
	],
	153018: [
		Item(153018, "Normal", "ABT", "Corrupted Mantle of the Felseekers"),
		Item(153018, "Heroic", "ABT", "Corrupted Mantle of the Felseekers"),
		# Item(153018, "Mythic", "ABT", "Corrupted Mantle of the Felseekers"),
	],
	165925: [
		Item(165925, "Raid Finder", "BoD", "Drape of Valiant Defense"),
		# Item(165925, "Normal", "BoD", "Drape of Valiant Defense"),
	],
	168602: [
		Item(168602, "Raid Finder", "EP", "Cloak of Blessed Depths"),
		# Item(168602, "Normal", "EP", "Cloak of Blessed Depths"),
		Item(168602, "Heroic", "EP", "Cloak of Blessed Depths"),
		Item(168602, "Mythic", "EP", "Cloak of Blessed Depths"),
	],
	184778: [
		Item(184778, "Mythic", "CN", "Decadent Nathrian Shawl"),
		Item(184778, "Fated Mythic", "CN", "Decadent Nathrian Shawl"),
	],
	190631: [
		Item(190631, "Raid Finder", "SotFO", "Vandalized Ephemera Mitts"),
		Item(190631, "Normal", "SotFO", "Vandalized Ephemera Mitts"),
		Item(190631, "Heroic", "SotFO", "Vandalized Ephemera Mitts"),
		Item(190631, "Mythic", "SotFO", "Vandalized Ephemera Mitts"),
		Item(190631, "Fated Raid Finder", "SotFO", "Vandalized Ephemera Mitts"),
		Item(190631, "Fated Normal", "SotFO", "Vandalized Ephemera Mitts"),
		Item(190631, "Fated Heroic", "SotFO", "Vandalized Ephemera Mitts"),
		Item(190631, "Fated Mythic", "SotFO", "Vandalized Ephemera Mitts"),
	],
	190334: [
		Item(190334, "Mythic", "SotFO", "Origin"),
		Item(190334, "Fated Mythic", "SotFO", "Origin"),
	],
}

def get_header_auth():
	with open("credentials", "r") as c:
		client_id = c.readline().strip()
		client_secret = c.readline().strip()
	x = requests.post(
		AUTH_URL, 
		data={'grant_type': 'client_credentials'},
		auth=(client_id, client_secret))
	access_token = json.loads(x.text)["access_token"]
	return {"Authorization": "Bearer " + access_token}

def get_bonuses():
	with open(BONUSES_LIST_JSON, "r") as f:
		return json.loads(f.read())

def parse_ahs():
	bonuses = get_bonuses()
	bearer = get_header_auth()
	params = {
		"namespace": f"dynamic-{REGION}",
		"locale": "en_US",
	}

	out = {}
	for key in ITEMS:
		out[key] = []

	for ah, ah_name in connected_realm_ids.items():
		x = requests.get(
			f"{HOST}data/wow/connected-realm/{ah}/auctions", 
			headers=bearer, params=params)

		if x.status_code != 200:
			print("Failted to get AH data")
			print(x)

		auctions = json.loads(x.text)["auctions"]
		print(f"There are {len(auctions)} items for auction in {ah_name}")
		for auction in auctions:
			if (id := auction['item']['id']) in ITEMS:
				no_diff_id = True
				if auction["item"].get("bonus_lists"):
					for bonus_id in auction["item"]["bonus_lists"]:
						if not bonuses.get(str(bonus_id)):
							# logging.warning(f"{bonus_id} is not part of RaidBots' list of ids, it was found on this item {auction}")
							continue
						for item in ITEMS[id]:
							if (_t := bonuses[str(bonus_id)].get("tag", False)):
								no_diff_id = False
								if _t == item.diff:
									out[id].append({"item": item, "auction": auction, "realm": ah})
					if no_diff_id:
						for item in ITEMS[id]:
							if item.diff == "Normal":
								out[id].append({"item": item, "auction": auction, "realm": ah})
				else:
					out[id].append({"item": ITEMS[id][0], "auction": auction, "realm": ah})
	return out

def print_items_pretty(items):
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
						cheapest[identifier]["bidOnDiffRealm"] = item["realm"]
	
	sorted_items = []
	while len(cheapest):
		smallest = float("inf")
		smallest_key = ""
		for item_identifier, item in cheapest.items():
			if item["auction"]["buyout"] < smallest:
				smallest = item["auction"]["buyout"]
				smallest_key = item_identifier
		sorted_items.append(cheapest.pop(smallest_key))

	columns = {
		"id": 2,
		"name": 4,
		"diff": 4,
		"source": 6,
		"bid": 3,
		"buyout": 6,
		"realm": 5,
	}

	for column in columns.keys():
		for item in sorted_items:
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
					if bid > columns[column]:
						columns[column] = bid
				case "buyout":
					buyout = len(str(round(
						item["auction"]["buyout"]/10000000))) + 1
					if buyout > columns[column]:
						columns[column] = buyout
				case "realm":
					if len(connected_realm_ids[item["realm"]]) > columns[column]:
						columns[column] = len(connected_realm_ids[item["realm"]])

	def pad_value(val, pad):
		return str(val) + " "*(pad - len(str(val)))

	line = f'| {pad_value("ID", columns["id"])} | {pad_value("Name", columns["name"])} | {pad_value("Diff", columns["diff"])} | {pad_value("Source", columns["source"])} | {pad_value("Bid", columns["bid"])} | {pad_value("Buyout", columns["buyout"])} | {pad_value("Realm", columns["realm"])} |'
	print(line)
	print("-"*len(line))
	for item in sorted_items:
		id = pad_value(item["item"].id, columns["id"])
		name = pad_value(item["item"].name, columns["name"])
		diff = pad_value(item["item"].diff, columns["diff"])
		source = pad_value(item["item"].source, columns["source"])
		_bid = str(round(item["auction"].get("bid", -10000000)/10000000)) + "k"
		bid = pad_value(_bid if _bid != "-1k" else "-", columns["bid"])
		buyout = pad_value(str(round(item["auction"]["buyout"]/10000000)) + "k", columns["buyout"])
		realm = pad_value(connected_realm_ids[item["realm"]], columns["realm"])
		line = f'| {id} | {name} | {diff} | {source} | {bid} | {buyout} | {realm} |'
		print(line)

def main(args):
	relevant_items = parse_ahs()
	print_items_pretty(relevant_items)

if __name__ == '__main__':
	t0 = time.time()
	os.chdir(WORKING_DIR)

	# parse input
	parser = argparse.ArgumentParser(description=DESCRIPTION)
	parser.add_argument("-log", type=str, default="INFO", help="set log level for console output, WARNING/INFO/DEBUG")
	parser.add_argument("-logfile", type=str, default="0", help="sets file logging level, 0/CRITICAL/ERROR/WARNING/INFO/DEBUG, set to 0 to disable")
	
	args = parser.parse_args()

	# setting up logger to info on terminal and debug on file
	log_format=logging.Formatter(f'%(asctime)s {APP_NAME} v{VERSION} %(levelname)s:%(name)s:%(funcName)s %(message)s')
	
	if args.logfile != "0":
		file_handler = logging.FileHandler(filename=LOG_FILE, mode="a")
		file_handler.setLevel(getattr(logging, args.logfile.upper()))
		file_handler.setFormatter(log_format)
		logging.getLogger().addHandler(file_handler)
	
	stream_handler = logging.StreamHandler(sys.stdout)
	stream_handler.setLevel(getattr(logging, args.log.upper()))
	logging.getLogger().addHandler(stream_handler)

	if args.logfile != "0":
		logging.getLogger().setLevel(getattr(logging, args.logfile.upper()))
	else:
		logging.getLogger().setLevel(getattr(logging, args.log.upper()))

	logging.debug(f"Started with arguments: {sys.argv}")

	main(args)

	logging.info(f"Exited. Ran for {round(time.time() - t0, 3)}s")