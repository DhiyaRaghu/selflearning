"""Career Coach AI starter server. Standard library only; deploy behind HTTPS."""
from __future__ import annotations
import hashlib, hmac, json, os, re, secrets, sqlite3, time
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("CAREER_DB_PATH", ROOT / "career_coach.sqlite3"))
COOKIE = "career_session"
MAX_BODY = 4 * 1024 * 1024

def db():
    con=sqlite3.connect(DB_PATH, timeout=15); con.row_factory=sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'Job seeker', password_hash TEXT NOT NULL, salt TEXT NOT NULL, created INTEGER NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires INTEGER NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS progress (user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, score INTEGER NOT NULL DEFAULT 68, streak INTEGER NOT NULL DEFAULT 1, runs INTEGER NOT NULL DEFAULT 0, skills TEXT NOT NULL DEFAULT '[]', saved_jobs TEXT NOT NULL DEFAULT '[]', resume_name TEXT NOT NULL DEFAULT '')")
    con.commit(); return con

def pw_hash(password, salt): return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),240000).hex()
def json_bytes(obj): return json.dumps(obj,ensure_ascii=False).encode()

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT),**kwargs)
    def log_message(self,fmt,*args): print(f"{self.address_string()} {fmt % args}")
    def send_json(self,code,obj,headers=None):
        b=json_bytes(obj); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store')
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(b)
    def body(self):
        n=int(self.headers.get('Content-Length','0'))
        if n>MAX_BODY: raise ValueError('Request too large')
        return json.loads(self.rfile.read(n) or b'{}')
    def user(self,con):
        c=cookies.SimpleCookie(self.headers.get('Cookie',''))
        if COOKIE not in c:return None
        token=c[COOKIE].value
        row=con.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?',(hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()
        return row
    def state(self,con,u):
        p=con.execute('SELECT * FROM progress WHERE user_id=?',(u['id'],)).fetchone()
        return {'name':u['name'],'role':u['role'],'score':p['score'],'streak':p['streak'],'practiceRuns':p['runs'],'resumeSkills':json.loads(p['skills']),'savedJobs':json.loads(p['saved_jobs']),'resumeName':p['resume_name']}
    def do_GET(self):
        path=urlparse(self.path).path
        if path.startswith('/api/'):
            con=db()
            try:
                if path=='/api/health':return self.send_json(200,{'ok':True,'service':'career-coach'})
                u=self.user(con)
                if path=='/api/me':return self.send_json(200,{'user':({'email':u['email'],'state':self.state(con,u)} if u else None)})
                if not u:return self.send_json(401,{'error':'Please sign in.'})
                if path=='/api/state':return self.send_json(200,{'state':self.state(con,u)})
                return self.send_json(404,{'error':'Not found'})
            finally:con.close()
        if path=='/':self.path='/index.html'
        return super().do_GET()
    def do_POST(self):
        path=urlparse(self.path).path
        if not path.startswith('/api/'):return self.send_error(404)
        try:data=self.body()
        except Exception as e:return self.send_json(400,{'error':str(e)})
        con=db()
        try:
            if path in ('/api/register','/api/login'):
                email=str(data.get('email','')).strip().lower(); password=str(data.get('password','')); name=str(data.get('name','Learner')).strip()[:80]
                if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):return self.send_json(400,{'error':'Enter a valid email address.'})
                if len(password)<10:return self.send_json(400,{'error':'Use a password with at least 10 characters.'})
                if path.endswith('register'):
                    salt=secrets.token_hex(16)
                    try:
                        cur=con.execute('INSERT INTO users(email,name,password_hash,salt,created) VALUES(?,?,?,?,?)',(email,name or 'Learner',pw_hash(password,salt),salt,int(time.time())))
                        uid=cur.lastrowid; con.execute('INSERT INTO progress(user_id) VALUES(?)',(uid,)); con.commit()
                    except sqlite3.IntegrityError:return self.send_json(409,{'error':'An account with this email already exists.'})
                else:
                    u=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                    if not u or not hmac.compare_digest(u['password_hash'],pw_hash(password,u['salt'])):return self.send_json(401,{'error':'Email or password is incorrect.'})
                    uid=u['id']
                token=secrets.token_urlsafe(32); con.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,int(time.time())+30*86400)); con.commit()
                u=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
                cookie=f'{COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000'+('; Secure' if os.getenv('COOKIE_SECURE','0')=='1' else '')
                return self.send_json(200,{'user':{'email':u['email'],'state':self.state(con,u)}},{'Set-Cookie':cookie})
            u=self.user(con)
            if not u:return self.send_json(401,{'error':'Please sign in.'})
            if path=='/api/logout':
                c=cookies.SimpleCookie(self.headers.get('Cookie',''))
                if COOKIE in c:con.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(c[COOKIE].value.encode()).hexdigest(),)); con.commit()
                return self.send_json(200,{'ok':True},{'Set-Cookie':f'{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'})
            if path=='/api/profile':
                name=str(data.get('name','')).strip()[:80]; role=str(data.get('role','')).strip()[:100]
                if not name or not role:return self.send_json(400,{'error':'Name and target role are required.'})
                con.execute('UPDATE users SET name=?,role=? WHERE id=?',(name,role,u['id']));con.commit();return self.send_json(200,{'state':self.state(con,con.execute('SELECT * FROM users WHERE id=?',(u['id'],)).fetchone())})
            if path=='/api/progress':
                p=con.execute('SELECT * FROM progress WHERE user_id=?',(u['id'],)).fetchone(); runs=max(0,min(10000,int(data.get('practiceRuns',p['runs'])))); score=max(0,min(100,int(data.get('score',p['score'])))); streak=max(0,min(10000,int(data.get('streak',p['streak']))))
                skills=data.get('resumeSkills',json.loads(p['skills'])); saved=data.get('savedJobs',json.loads(p['saved_jobs']))
                if not isinstance(skills,list) or not isinstance(saved,list):return self.send_json(400,{'error':'Invalid progress data.'})
                con.execute('UPDATE progress SET score=?,streak=?,runs=?,skills=?,saved_jobs=? WHERE user_id=?',(score,streak,runs,json.dumps(skills[:30]),json.dumps(saved[:100]),u['id']));con.commit()
                return self.send_json(200,{'state':self.state(con,u)})
            if path=='/api/resume':
                filename=re.sub(r'[^\w. -]','_',str(data.get('filename','resume.txt')))[:120]; text=str(data.get('text',''))[:100000]
                if not text.strip():return self.send_json(400,{'error':'This first version can analyze pasted text or .txt files. PDF/DOCX parsing is not connected yet.'})
                known=['python','sql','excel','communication','leadership','data analysis','project management','javascript','research','java','public speaking','problem solving']
                found=[s.title() for s in known if re.search(r'\b'+re.escape(s)+r'\b',text,re.I)]
                skills=list(dict.fromkeys(found))[:12]
                con.execute('UPDATE progress SET resume_name=?,skills=? WHERE user_id=?',(filename,json.dumps(skills),u['id']));con.commit()
                return self.send_json(200,{'resumeName':filename,'skills':skills,'note':'Confirm these extracted skills before using them for matches.'})
            return self.send_json(404,{'error':'Not found'})
        finally:con.close()

if __name__=='__main__':
    host=os.getenv('HOST','0.0.0.0');port=int(os.getenv('PORT','8000'))
    print(f'Career Coach AI running at http://{host}:{port}')
    ThreadingHTTPServer((host,port),Handler).serve_forever()

