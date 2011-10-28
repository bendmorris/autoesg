from parameters import PARAMETERS

# general settings
RESULTS_FILE = "files_to_download.txt"
DOWNLOADS_FILE = "files_downloaded.txt"
DATA_STORES = [l + "/Databank/" for l in
               [
                "/export8_1", 
                "/export8_2", 
                "/export8_3",
                "/export8_4",
               ]
              ]
SERVERS = {
           "ncar":  "http://www.earthsystemgrid.org/",
           "pcmdi":  "http://pcmdi3.llnl.gov/esgcet/",
           "nci":   "http://esg.nci.org.au/esgcet/",
           "badc":  "http://cmip-gw.badc.rl.ac.uk/",
           "nersc": "http://esg.nersc.gov/esgcet/",
           "ornl":  "http://esg2-gw.ccs.ornl.gov/",
           "jpl":   "http://esg-gateway.jpl.nasa.gov/",
           "wdcc":  "http://ipcc-ar5.dkrz.de/",
           }
DEFAULT_SERVER = "pcmdi"
USERNAME = "bendmorris"
PASSWORD = None
OPENID = "https://pcmdi3.llnl.gov/esgcet/myopenid/bendmorris"
#OPENID = "https://www.earthsystemgrid.org/esgcet/myopenid/bendmorris"
