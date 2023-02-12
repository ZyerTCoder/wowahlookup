# wowahlookup

Grabs AH data from chosen servers and lists the cheapest items it finds, example output:
```
| ID     | Name                               | Diff              | Source        | Bid  | Buyout | Realm       | Ratio | MarketV |
-----------------------------------------------------------------------------------------------------------------------------------
| 118790 | Sabre of the Faceless Moon         | Normal            | WoD World     | 5k   | 6k     | Tarren Mill | 0.12  | 46k     |
| 118791 | Razorcrystal Blade                 | Normal            | WoD World     | 19k  | 20k    | Tarren Mill | 0.19  | 100k    |
| 118808 | Highmaul Magi Scarf                | Normal            | WoD World     | 19k  | 20k    | Tarren Mill | 0.11  | 170k    |
| 2244   | Krol Blade                         | Normal            | Classic World | 23k  | 24k    | Tarren Mill | 0.3   | 77k     |
| 116572 | Skettis Staff                      | Normal            | WoD World     | -    | 25k    | Defias      | 0.46  | 55k     |
| 11168  | Formula: Shield Lesser Parry       | Normal            | Classic World | 24k  | 25k    | Tarren Mill | 0.26  | 93k     |
| 190631 | Vandalized Ephemera Mitts          | Fated Raid Finder | SotFO         | -    | 25k    | Tarren Mill | 0.31  | 80k     |
| 118809 | Eldodin's Elegant Drape            | Normal            | WoD World     | 28k  | 30k    | Tarren Mill | 0.17  | 169k    |
| 118804 | Starrgo's Walking Stick            | Normal            | WoD World     | -    | 35k    | Tarren Mill | 0.22  | 160k    |
.
.
.
```

Requires your own set of blizzard and tsm authentication credentials which you can find on their [developer](https://develop.battle.net/documentation/guides/getting-started) [websites](https://www.tradeskillmaster.com/user).
In the /required/ directory, create "blizzard_credentials.txt" containing the client id on the first line and the secret id on the second and create "tsm_credentials.txt" containing just the tsm api key.

Relevant globals can be changed at the top of the python script including your region (only tested for eu) and realms of interest.

Files created in /local/ can be deleted without consequence as they only exist to make subsequent runs faster and reduce api calls.
