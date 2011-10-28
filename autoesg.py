#!/usr/bin/python
#
# AutoESG: script to automatically download CMIP data
#
# usage: python autoesg.py [-u username] 
#                          [-p password]
#                          [-g]
#                          [-s server]
#                          [-t timeout]
# -u    login username
# -p    login password
# -g    run in graphical mode (show browser windows)
# -s    choose server (llnl or nci)
# -t    time to wait for page loads, in seconds, before timing out
#
# When autoesg.py is run, it will store a list of files to download in
# files_to_download.txt. You should then run download.py to download
# the files.

import os
import os.path
import re
import sys
import time
import traceback
from copy import deepcopy
from getpass import getpass
import spynner
from pyquery import PyQuery as P
from BeautifulSoup import BeautifulSoup as soup
from PyQt4.QtCore import QUrl
from PyQt4.QtGui import QApplication
from config import *
        

LOGFILE = "autoesg_log.txt"
ERR_LOGFILE = "autoesg_err.txt"
LOAD_TIMEOUT = 60
USE_OPENID = False

# get initial arguments
server = DEFAULT_SERVER
arguments = sys.argv
graphical = False

n = 1
while n < len(sys.argv):
    a = sys.argv[n]
    
    try:
        if a == "-u" or a == "--user":
            USERNAME = sys.argv[n + 1]
            n += 1
        elif a == "-p" or a == "--pass":
            PASSWORD = sys.argv[n + 1]
            n += 1
        elif a == "-o" or a == "--openid":
            OPENID = sys.argv[n + 1]
            n += 1
        elif a == "-g" or a == "--graphical":
            graphical = True
        elif a == "-s" or a == "--server":
            if server in SERVERS.keys():
                server = sys.argv[n + 1]
            else:
                print "Unknown server:", server
            n += 1
        elif a == "-f" or a == "--file":
            RESULTS_FILE = sys.argv[n+1]
            n += 1
        elif a == "-t" or a == "--timeout":
            LOAD_TIMEOUT = int(sys.argv[n+1])
            n += 1
        elif a == "--useopenid":
            USE_OPENID = True
        else:
            print "Unknown argument:", a
        

    except IndexError:
        print "No argument to", a
        pass
        
    n += 1        

if not USERNAME:
    USERNAME = raw_input("Username: ")
if not PASSWORD:
    PASSWORD = getpass()


DOMAIN = SERVERS[server]
URL = DOMAIN + "home.htm"
DATA_URL = DOMAIN + "query/advanced.htm"

    
def get_log(mode, filepath=LOGFILE):
    try:
        os.open(filepath, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except:
        pass
    f = file(filepath, mode)
    return f
    
    
already_downloaded = set()    
log = get_log("r")
for line in log:
    already_downloaded.add(line.replace("\n", ""))
log.close()

already_added = set()
f = open(RESULTS_FILE)
for line in f:
    already_added.add(line.replace("\n", ""))
f.close()


def fix_html(html):
    patterns = [
                r'="/[^"]*?"',
                r"='/[^']*?'",
                r'\("/[^"]*?"',
                r"\('/[^']*?'",
                ]
    urls = []
    for pattern in patterns:
        urls += re.findall(pattern, html)
    domain = '/'.join(DOMAIN.split("/")[0:3])
    for url in set(urls):
        replace = url[0:2] + domain + url[2:]
        #print url, replace
        html = html.replace(url, replace)
    return html
    
    
def format_value(name, value):
    value = value.lower().replace(" ", "_")
    if name == "project":
        return ("hasProject", "esg:project_" + value)
    elif name == "model":
        return ("hasModel", "esg:" + 
                            ("model_" if value[:6] != "model_" else "") 
                            + value)
    elif name == "experiment":
        return ("hasExperiment", "esg:experiment_" + value)
    elif name == "frequency":
        return ("hasTimeFrequency", "esg:timefrequency_" + value)
    elif name == "realm":
        return ("hasRealm", "esg:topic_" + value)
    elif name == "variable":
        return ("hasCFParameter", "cf:" + value)


app = QApplication([])


class Browser(spynner.Browser):
    def __init__(self, params={}, cookies=None):
        self.params = params
        spynner.Browser.__init__(self, app=app)
        self.shown = False
        self.set_html_parser(P)
        self.finished = False
        self.parameter = 0
        if cookies:
            self.set_cookies(cookies)
            
            
    def get_url(self):return str(self.webframe.url().toString())        
    def set_url(self, url):self.webframe.setUrl(QUrl(DATA_URL))
    def get_html(self):return str(self.webframe.toHtml())
    def set_html(self, html):self.webframe.setHtml(html)
        
    url = property(get_url, set_url)
    html = property(get_html, set_html)
            
    def param_description(self):
        return (">>".join(
                 [self.params[key]
                  for key in [p[0] for p in PARAMETERS]
                  if self.params.has_key(key)]))
                  
                  
    def data_download_path(self):
        base_path = ""
        full_path = (base_path + 
                     '/'.join([self.params[p[0]]
                               for p in PARAMETERS
                               if self.params.has_key(p[0])
                               and p[2]])) + "/"
        return full_path
            
            
    def log_exception(self):
        s = self.param_description()
        print "*** Failed on download:", s, "***" 
        
        cla, exc, trbk = sys.exc_info()
        sys.stderr.write(time.strftime('%x %X'))
        sys.stderr.write('\n')
        sys.stderr.write(self.url)
        sys.stderr.write('\n')
        sys.stderr.write(cla.__name__ + ", " + s)
        sys.stderr.write('\n')
        sys.stderr.write(str(exc))
        sys.stderr.write('\n')
        for t in traceback.format_tb(trbk, 2):
            sys.stderr.write(t)
        sys.stderr.write('\n')
        sys.stderr.write('\n')
        sys.stderr.flush()
      
        self.close()
            
            
    def close(self):
        self.finished = True
        self.shown = False
        if self.webview:
            self.destroy_webview()
        #spynner.Browser.close(self)
        #self.application.exit()
        
        
    def show(self, force=False):
        if graphical or force:
            self.shown = True
            self.create_webview()
            spynner.Browser.show(self)


    def go_to_url(self, url):
        sys.stdout.write("==> " + url + "... ")
        sys.stdout.flush()
        
        try:
            success = self.load(url)
        except:
            success = False
            
        if not success:
            print
            raise Exception("Failed to load " + url)
            
        print "done."

                
    def go_to_link(self, name):
        link = self.search_element_text(name)[0]
        if not link:
            raise Exception("Couldn't find %s link." % name)
            
        self.click_link('a:contains("' + name + '")')
        print "==> " + name
        
        
    def on_login_page(self):
        return (
                (not self.text_on_page("j_username")) and
                (not self.text_on_page("j_password"))
                ) or (not self.text_on_page("openid_identifier"))
                

    def login(self, timeout=LOAD_TIMEOUT):
        if self.on_login_page():
            # fill out login form and hit submit
            try:
                if USE_OPENID:
                    raise Exception()
                self.fill("input[name=j_username]", USERNAME)
                self.fill("input[name=j_password]", PASSWORD)
                print "Login:", USERNAME, ''.join(["*" for c in PASSWORD])
                self.click("button#login-button-button", wait_load=True)
            except:
                self.fill("input[name=openid_identifier]", OPENID)
                print "Login:", OPENID, ''.join(["*" for c in PASSWORD])
                self.click("button#openid-button-button", wait_load=True)
                self.fill("input[name=j_password]", PASSWORD)
                self.click("button#login-button-button", wait_load=True)

            if self.on_login_page():
                raise Exception("Login failed.")

            print "Login successful."

        
    def loading(self, name):
        return not ("any " + name.lower() in str(self.soup("fieldset").find("div#facets_div").find("div.myAccordion")).lower())
        
        
    def text_on_page(self, text):
        return not (text.lower() in self.html.lower())

       
    def wait_for_load(self, text, message, loading=None, wait_first=True,
                      timeout=LOAD_TIMEOUT, initial_delay=1, name=""):
        self.wait(initial_delay)
        
        sys.stdout.write(message)
        sys.stdout.flush()
        
        for b in ((False, True) if wait_first else (True,)):
            loops = 0
            while loading(self, text) == b and loops < timeout:
                loops += 1
                self.wait(1)
                
                if "internal server error" in self.html.lower():
                    raise Exception("Internal server error.")

                if self.on_login_page():
                    self.login()
                
            if loops >= timeout:
                raise Exception("Wait for loading timed out.")
            
        print "done."


    def on_page(self, value, page=None, in_tag=False):
        if page == None:
            page = str(self.soup("fieldset"))
        if in_tag:
            value = ">" + value + "<"
        return value.lower() in page.lower()


    def set_property(self, name, value, jsvalue, initial_delay=1):
        self.wait(initial_delay)
        
        fv = format_value(name, jsvalue)
        set_facet = 'setFacet("' + fv[0] + '", "' + fv[1] + '");'
        self.runjs(set_facet)
        
        self.wait_for_load(name, name + " = " + value + "... ", 
                           loading=Browser.loading)
        if self.on_page("results: 0", page=self.html):
            raise Exception("0 results!")

        
    def new_browser(self):
        new_browser = Browser(params=deepcopy(self.params), 
                              cookies=self.get_cookies())
        new_browser.parameter = self.parameter
        new_html = fix_html(self.html)
        
        new_browser.url = DATA_URL
        new_browser.html = new_html
        
        new_browser.load_jquery()
        new_browser.show()
        
        return new_browser
        
        
    def try_to(self, f, e):
        try:
            f()
            return True
        except:
            e()
            return False
        

    def filter_parameter(self):
        if self.parameter >= len(PARAMETERS):
            self.params["result"] = 0
            success = self.download_results_page()
            if success:
                self.finish()
                return True
            else:
                self.close()
                return False
        else:
            param_name, items, _ = PARAMETERS[self.parameter]
            valid = []
            for item in items:
                if isinstance(item, tuple):
                    value = item[0]
                else:
                    value = item
                if self.on_page(value, in_tag=True):
                    valid.append(item)
            print param_name + ":", valid
            
            errors = False
            for item in valid:
                if isinstance(item, tuple):
                    real_name, js_name = item
                else:
                    real_name = js_name = item
                self.params[param_name] = real_name            
                if not self.param_description() in already_downloaded:
                    new_browser = self.new_browser()
                    new_browser.parameter += 1
                    
                    try:
                        new_browser.set_property(param_name, 
                                                 real_name,
                                                 js_name
                                                 )
                        success = new_browser.filter_parameter()
                        if not success:
                            errors = True
                    except:                    
                        new_browser.log_exception()
                        errors = True
                        
            if param_name in self.params.keys():
                self.params.pop(param_name)
                
            if not errors:
                self.finish()
                return True
            else:
                self.close()
                return False

    
    def download_results_page(self):
        self.wait(10)
        
        print "Downloading results page", (self.params["result"] / 10) + 1
        
        new_browser = self.new_browser()
        try:
            success = new_browser.download_wget_script()
        except:
            self.log_exception()
            success = False
        
        self.params["result"] += 10
        next_page_js = ("javascript: submitQuery(" + 
                        str(self.params["result"]) + ")")
        more_pages = self.on_page(next_page_js,
                                  page=self.html)

        if more_pages:
            print "(More results pages)"
            new_browser = self.new_browser()
            new_browser.runjs(next_page_js)
            new_browser.wait(10)
            try:
                success = (success and new_browser.download_results_page())
            except:
                self.log_exception()
                return False
        return success
        
        
    def get_url_from_path(self, path):
        try:
            if path[0] == "/":
                return "http://" + str(self.webframe.url().host()) + path
            else:
                return path
        except:
            return path
        
    
    def download_wget_script(self):
        self.check(":checkbox")
        self.wait(5)
        self.runjs("downloadFiles();")
        try:
            self.wait_for_load("download selected data",
                               "Loading download page 1... ",
                               initial_delay=0,
                               wait_first=False,
                               loading=Browser.text_on_page)
        except:
            self.log_exception()
            return False
            
        self.wait(1)
        self.runjs("document.form0.submit();")
        self.wait(1)
        self.wait_for_load("file download selection",
                           "Loading download page 2... ",
                           initial_delay=0,
                           wait_first=False,
                           loading=Browser.text_on_page)
        self.wait(5)
        
        rows = [P(row).find('a')
                for row in P(self.html)("form#downloadForm")("table")
                if len(P(row).find('a')) == 2
                ]
        files = [row[1].get('href') for row in rows]
        
        for this_file in files:
            new_dl = ', '.join([
                                self.data_download_path(),
                                self.get_url_from_path(this_file),
                                ]
                               )
            if not new_dl in already_added:
                downloads.write(new_dl + '\n')
        downloads.flush()
        print ">>>> Wrote new files to " + RESULTS_FILE
        self.close()
        return True
        

    def finish(self):
        log.write(self.param_description() + "\n")
        log.flush()
        already_downloaded.add(self.param_description())    
        self.close()



browser = Browser()
browser.go_to_url(URL)
browser.show()

# go to login page
browser.go_to_link("Login")
login_url = browser.url
browser.login()


log = get_log("a")
downloads = open(RESULTS_FILE, "a")
sys.stderr = get_log("a", ERR_LOGFILE)
cookies = browser.get_cookies()
browser.go_to_url(DATA_URL)

def main():
    try:
        browser.wait(1)
        browser.filter_parameter()
    except:
        browser.log_exception()


main()
sys.stderr = sys.__stderr__
downloads.close()
log.close()

browser.close()
app.exit()

print "Finished!"
