import subprocess, os, sqlite3

def check_profile(prof):
    src = f"C:\\Users\\imgk3\\AppData\\Local\\Google\\Chrome\\User Data\\{prof}\\Network\\Cookies"
    dst = f"m:\\chakramodel\\scratch\\cookies_{prof}.db"
    
    ps_cmd = f"powershell -Command \"Copy-Item -Path '{src}' -Destination '{dst}' -Force\""
    subprocess.run(ps_cmd, shell=True)
    
    if os.path.exists(dst):
        try:
            conn = sqlite3.connect(dst)
            c = conn.cursor()
            c.execute("SELECT host_key, name FROM cookies WHERE host_key LIKE '%kaggle%'")
            rows = c.fetchall()
            print(f"Profile {prof} Kaggle cookies count:", len(rows))
            for r in rows:
                print(' ', r[0], r[1])
            conn.close()
        except Exception as e:
            print(f"Error reading {prof} db:", e)

check_profile('Default')
check_profile('Profile 2')
