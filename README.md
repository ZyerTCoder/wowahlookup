# wowahlookup

Grabs AH data from chosen servers and lists the cheapest items it finds, example output:
```
| ID     | Name                         | Diff              | Source  | Bid  | Buyout | Realm       |
-----------------------------------------------------------------------------------------------------
| 190631 | Vandalized Ephemera Mitts    | Fated Raid Finder | SotFO   | -    | 75k    | Tarren Mill |
| 142541 | Drape of the Forgotten Souls | Mythic            | ToV     | -    | 80k    | Tarren Mill |
| 190631 | Vandalized Ephemera Mitts    | Fated Heroic      | SotFO   | -    | 80k    | Tarren Mill |
| 187019 | Infiltrator's Shoulderguards | Normal            | Korthia | 180k | 120k   | Defias      |
| 184778 | Decadent Nathrian Shawl      | Fated Mythic      | CN      | 475k | 150k   | Tarren Mill |
| 190631 | Vandalized Ephemera Mitts    | Mythic            | SotFO   | -    | 177k   | Tarren Mill |
| 190334 | Origin                       | Mythic            | SotFO   | -    | 200k   | Tarren Mill |
| 190334 | Origin                       | Fated Mythic      | SotFO   | -    | 218k   | Tarren Mill |
| 187097 | Construct's Shoulderplates   | Normal            | Korthia | 315k | 350k   | Tarren Mill |
| 190631 | Vandalized Ephemera Mitts    | Fated Mythic      | SotFO   | -    | 350k   | Aggra       |
```

Requires your own set of blizzard authentication credentials which you can find on their [developer website](https://develop.battle.net/documentation/guides/getting-started), create a textfile named "credentials" in the same directory as the python script and paste the client and secret ids on the first and second lines respectively

Relevant globals can be changed at the top of the python script