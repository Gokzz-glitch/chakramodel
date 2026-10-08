import argparse
import time
import urllib.request
import urllib.error
import datetime

def monitor(url, log_file, interval):
    while True:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                status = response.getcode()
                log_message = f"[{now}] URL: {url} | Status: {status}\n"
        except urllib.error.URLError as e:
            code = getattr(e, 'code', str(e.reason))
            log_message = f"[{now}] URL: {url} | Error: {code}\n"
        except Exception as e:
            log_message = f"[{now}] URL: {url} | Error: {str(e)}\n"
        
        with open(log_file, "a") as f:
            f.write(log_message)
            
        print(log_message.strip(), flush=True)
        time.sleep(interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor a URL.")
    parser.add_argument("--url", required=True, help="URL to monitor")
    parser.add_argument("--log", required=True, help="Log file path")
    parser.add_argument("--interval", type=int, default=360, help="Interval in seconds")
    args = parser.parse_args()
    
    monitor(args.url, args.log, args.interval)
