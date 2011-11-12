#!/usr/bin/python
#
# script to automatically download CMIP data
#
# usage: python download.py [-u username] 
#                           [-p password]
#                           [-f path]
# -u    login username
# -p    login password
# -f    specify the path of the files_to_download file

from threading import Thread, Lock
import gc
import os
import re
import shutil
import sys
import time
from urllib2 import URLError
from getpass import getpass
import mechanize
from config import *
    

LOG_FILE = "download_log.txt"
LOGIN_URL = "http://pcmdi3.llnl.gov/esgcet/ac/guest/secure/sso.htm"
MAX_THREADS = 10

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
        elif a == "-f" or a == "--file":
            RESULTS_FILE = sys.argv[n+1]
            n += 1
        elif a == "-t" or a == "--threads":
            MAX_THREADS = int(sys.argv[n+1])
            n += 1
        else:
            print "Unknown argument: " + a
        

    except IndexError:
        print "No argument to " + a
        pass
        
    n += 1        

if USERNAME == None:
    USERNAME = raw_input("Username: ")
if PASSWORD == None:
    PASSWORD = getpass()

def dir_fill(path):
    make_dirs(path)
    try:
        f = os.statvfs(path).f_bfree
        a = os.statvfs(path).f_blocks
        return float(a - f) / a
    except:
        return 1.0
    
def next_data_store():
    for data_store in DATA_STORES:
        
        if dir_fill(data_store) < 0.9:
            return data_store
    return ""
    
def make_dirs(path):
    try:
        os.makedirs(path)
    except:
        pass

log_file = open(LOG_FILE, "a")
downloads_started = set()
output_lock = Lock()
finished_lock = Lock()
downloads_started_lock = Lock()


class Logger:
    def write(self, t):
        output_lock.acquire()
        if t.replace("\n", "").strip():
            message = time.strftime('%x %X ') + t + "\n"
            sys.__stdout__.write(message)
            sys.__stdout__.flush()
            log_file.write(message)
            log_file.flush()
        output_lock.release()
    def flush(self):pass
        

class DownloadThread(Thread):
    def __init__(self, n, this_file, finished_log):
        Thread.__init__(self)
        self.n = n
        self.this_file = this_file
        self._started = False
        self._finished = False
        self._downloading = False
        self.finished_log = finished_log
        self.downloaded = 0
        self.temp_file_path = None
        self.daemon = True

    def started(self):
        return self._started
        
    def downloading(self):
        return self._downloading
        
    def finished(self):
        return self._finished
        
    def start(self):
        self._started = True
        self.browser = mechanize.Browser(history=NoHistory())
        self.browser.set_handle_robots(False)
        Thread.start(self)
        
    def run(self):
        this_file = self.this_file
        b = self.browser
        try:
            download_path = next_data_store() + this_file[0]
            make_dirs(download_path)
                
            response = b.open(this_file[1])
            if b.geturl()[-4:] == ".htm":
                response = self.login(time.time())
            
            # filenames = (re.findall(r"/[^/]*?.nc\?", b.geturl()) +
            #              re.findall(r"/[^/]*?.nc", b.geturl()))
            
            filename = b.geturl().split("/")[-1].split("?")[0]
            if not filename[-3:] == ".nc":
                raise Exception("Download target " + filename + " is not a .nc file.")
            downloads_started_lock.acquire()
            exists = filename in downloads_started
            downloads_started_lock.release()
            if not exists:
                for data_store in DATA_STORES:
                    if os.path.exists(data_store + this_file[0] + filename):
                        exists = data_store + this_file[0]
            if exists:
                print str(self.n) + ": " + filename + " already exists at " + exists
            else:
                downloads_started_lock.acquire()
                downloads_started.add(filename)
                downloads_started_lock.release()            
                path = download_path + filename
                nds = next_data_store()
                self.temp_file_path = next_data_store()
                make_dirs(self.temp_file_path)
                self.temp_file_path += "temp." + str(self.n)
                save_file = open(self.temp_file_path, "wb")
                self._downloading = True
                
                response = response.wrapped.fp
                data = response.read(1024)
                print str(self.n) + ": Downloading " + filename + " to " + download_path + " ..."
                while len(data):
                    self.downloaded += len(data)
                    save_file.write(data)
                    save_file.flush()
                    data = response.read(1024)
                save_file.close()
                shutil.move(self.temp_file_path, path)
                
                print str(self.n) + ": Download finished."
            finished_lock.acquire()
            self.finished_log.write(', '.join(this_file) + "\n")
            self.finished_log.flush()
            finished_lock.release()
                
        except Exception as e:
            print str(self.n) + ": " + str(this_file)
            print str(self.n) + ": " + str(e)

        b.close()
        self._finished = True        
        
        
    def first_form_control(self, form_number=0):
        b = self.browser
        b.select_form(nr=form_number)
        forms = b.forms()
        try:
            for i in range(form_number + 1):
                form = forms.next()
            try:
                return form.find_control(type="text").pairs()[0][0]
            except:
                return form.find_control(type="password").pairs()[0][0]
        except StopIteration:
            return ""
            
            
    def submit(self):
        try:
            self.browser.submit()
        except:
            pass
        
            
    def login(self, start_time, attempts=0, timeout=120):
        if attempts >= 10:
            raise Exception("Too many attempts to log in.")
    
        b = self.browser
        
        if time.time() - start_time > timeout:
            raise Exception("Login timed out.")
        filename = b.geturl().split("/")[-1].split("?")[0]

        try:
            if filename[-3:] == ".nc":
                return b.response()
            else:
                try:
                    first_input = self.first_form_control()
                    if first_input == "j_username":
                        #b["j_username"] = USERNAME
                        #b["j_password"] = PASSWORD
                        first_input = self.first_form_control(1)
                        #self.submit()
                    if first_input == "openid_identifier":
                        b["openid_identifier"] = OPENID
                        #print "openid=" + OPENID
                        self.submit()
                    if first_input == "j_password":
                        b["j_password"] = PASSWORD
                        #print PASSWORD
                        self.submit()
                    #else:
                        #raise Exception("Login failed, reached page " + filename)
                except mechanize._mechanize.FormNotFoundError:
                    b.open(self.this_file[1])
                    
            filename = b.geturl().split("/")[-1].split("?")[0]
            if filename[-3] == ".nc":
                return b.response()
            else:
                return self.login(start_time, attempts=attempts+1)


        except URLError as e:
            #print "urlerror"
            filename = b.geturl().split("/")[-1].split("?")[0]
            if filename == "home.htm":
                b.open(self.this_file[1])
            return self.login(start_time, attempts=attempts+1)
        
            
    
def wait(waittime):
    itime = time.time()
    while time.time() - itime < waittime:
        pass
    
class NoHistory(object):
    def add(self, *a, **k): pass
    def clear(self): pass
    def close(self): pass
    
sys.stdout = sys.stderr = Logger()

def main():
    threads = []
    try:
        results = open(RESULTS_FILE, "r")
        all_files = []
        for line in results:
            if line and len(line.split(",")) > 1:
                this_file = tuple([s.strip() for s in line.split(",")])
                all_files.append(this_file)
        results.close()

        already_downloaded = set()
        finished = open(DOWNLOADS_FILE, "r")
        for line in finished:
            if line and len(line.split(",")) > 1:
                this_file = tuple([s.strip() for s in line.split(",")])
                already_downloaded.add(this_file)
        finished.close()

        n = len([f for f in all_files if not f in already_downloaded])
        print str(n) + " files to download"
        if n == 0:
            return

        n = 0

        finished = open(DOWNLOADS_FILE, "a")
        for this_file in all_files:
            if not this_file in already_downloaded:
                n += 1
                threads.append(DownloadThread(n, this_file, finished))
        done = 0
        
        start_time = time.time()
        loops = 0
        total_size = 0
        while done < n:
            loops += 1
            finished_threads = [t for t in threads if t.finished()]
            done = len(finished_threads)
            
            running = len([t for t in threads if t.started() and not t.finished()])
            downloading = len([t for t in threads if t.downloading() and not t.finished()])
            
            for t in threads:
                if t.started() and not t.finished():
                    chunk = t.downloaded
                    total_size += chunk
                    t.downloaded -= chunk
            
            if running < MAX_THREADS:
                for t in [t for t in threads
                          if not t.started()][:MAX_THREADS - running]:
                    t.start()
                    running += 1

            if loops % 6 == 0:
                elapsed_time = time.time() - start_time
                print ("Downloading " + str(downloading) + " of " + str(len(threads) - done) + " files, " +
                       ("%.2f" % (total_size / (elapsed_time * (1000 ** 2)))) + " MB/sec")        
                start_time = time.time()
                total_size = 0
                loops = 0
                
            for t in finished_threads:
                threads.remove(t)
                    
            wait(10)
                
        finished.close()
        main()
        
    except KeyboardInterrupt:
        for thread in threads:
            if thread.temp_file_path:
                os.remove(thread.temp_file_path)
        sys.exit()
    
            
main()
print "All downloads finished."
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__
log_file.close()
