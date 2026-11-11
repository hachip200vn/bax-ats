#!/usr/bin/env python3
"""BAX ATS + Career Site – backend chạy localhost (chỉ dùng thư viện chuẩn Python 3.8+).
Cổng 3000: Career Site (ứng viên) – chỉ có /public/*.  Cổng 3001: ATS nội bộ – có thêm /api/*.
Dữ liệu lưu trong bax.db (SQLite). Xoá file này để về dữ liệu mẫu ban đầu."""
import json, os, re, sqlite3, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB = ROOT / "bax.db"
LOCK = threading.Lock()
HITS = {}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    with conn() as c:
        c.execute("create table if not exists state(id integer primary key check(id=1), rev integer not null, json text)")
        c.execute("insert or ignore into state values(1,0,null)")
        c.execute("create table if not exists audit(id integer primary key autoincrement, at text, action text, detail text)")

def get_state():
    with conn() as c:
        r = c.execute("select rev,json from state where id=1").fetchone()
    return r["rev"], (json.loads(r["json"]) if r["json"] else None)

def audit(action, detail=""):
    with conn() as c:
        c.execute("insert into audit(at,action,detail) values(?,?,?)", (time.strftime("%Y-%m-%d %H:%M:%S"), action, detail[:300]))

def put_state(rev, state):
    """Ghi toàn bộ trạng thái nếu rev khớp (chống ghi đè dữ liệu mới hơn)."""
    with LOCK, conn() as c:
        cur = c.execute("select rev from state where id=1").fetchone()["rev"]
        if rev != cur:
            return None
        c.execute("update state set rev=?, json=? where id=1", (cur + 1, json.dumps(state, ensure_ascii=False)))
        return cur + 1

def mutate(fn):
    """Áp một thay đổi lên trạng thái, tăng rev. fn nhận state và trả về kết quả hoặc ném ValueError."""
    with LOCK, conn() as c:
        r = c.execute("select rev,json from state where id=1").fetchone()
        st = json.loads(r["json"]) if r["json"] else None
        if st is None:
            raise ValueError("ATS chưa khởi tạo dữ liệu. Hãy mở ATS (cổng 3001) một lần trước.")
        out = fn(st)
        c.execute("update state set rev=?, json=? where id=1", (r["rev"] + 1, json.dumps(st, ensure_ascii=False)))
        return out

def today():
    return time.strftime("%Y-%m-%d")

def score(job, cv):
    sk = [s.strip() for s in (job.get("sk") or "").split(",") if s.strip()]
    low = cv.lower()
    ok = [s for s in sk if s.lower() in low]
    m = re.search(r"(\d+)\s*(năm|years?)", cv, re.I)
    y = int(m.group(1)) if m else 0
    return round(len(ok) / (len(sk) or 1) * 70 + min(y / (job.get("me") or 1), 1) * 30)

def new_id(st):
    st["nid"] = st.get("nid", 10) + 1
    return st["nid"] - 1

def public_jobs(st):
    return [{"id": j["id"], "t": j["t"], "d": j["d"], "loc": j.get("l") or "Thành phố Hồ Chí Minh",
             "ty": j.get("ty") or "Official", "jd": j.get("jd", "")}
            for j in (st or {}).get("jobs", []) if "Career Site" in j.get("ch", [])]

def public_news(st):
    return [{"id": n["id"], "t": n["t"], "s": n.get("s", ""), "d": n["d"]} for n in (st or {}).get("news", [])]

def need(b, key, maxlen):
    v = str(b.get(key, "")).strip()
    if len(v) > maxlen:
        raise ValueError("Nội dung quá dài")
    return v

def apply_job(b):
    if b.get("consent") is not True:
        raise ValueError("Cần đồng ý xử lý dữ liệu cá nhân")
    n, e, p, cv, ref = need(b, "n", 120), need(b, "e", 200), need(b, "p", 30), need(b, "cv", 8000), need(b, "ref", 60)
    if not n or not cv or not EMAIL.match(e):
        raise ValueError("Nhập đúng họ tên, email và nội dung hồ sơ")
    def fn(st):
        job = next((j for j in st["jobs"] if j["id"] == b.get("jid") and "Career Site" in j.get("ch", [])), None)
        if not job:
            raise ValueError("Vị trí này không còn mở")
        if any(c["e"].lower() == e.lower() and c["j"] == job["id"] and not c.get("del") for c in st["cands"]):
            raise ValueError("Bạn đã ứng tuyển vị trí này")
        c = {"id": new_id(st), "n": n, "e": e, "p": p, "j": job["id"], "cv": cv, "src": "Referral" if ref else "Career Site",
             "ref": ref, "st": 0, "mx": 0, "at": today(), "tags": [], "m": [], "sc": [], "iv": [], "ai": score(job, cv)}
        text = "Chào %s, BAX cảm ơn bạn đã ứng tuyển vị trí %s. Chúng tôi sẽ phản hồi sớm." % (n, job["t"])
        c["m"].append({"k": "Thư cảm ơn", "ch": "Email", "t": text, "d": today()})
        st["cands"].append(c)
        st.setdefault("log", []).insert(0, "%s · Email “Thư cảm ơn” → %s" % (today(), n))
        return {"id": c["id"]}
    out = mutate(fn)
    audit("application.created", "%s → job %s" % (e, b.get("jid")))
    return out

def join_talent(b):
    if b.get("consent") is not True:
        raise ValueError("Cần đồng ý xử lý dữ liệu cá nhân")
    n, e, cv = need(b, "n", 120), need(b, "e", 200), need(b, "cv", 4000)
    if not n or not EMAIL.match(e):
        raise ValueError("Nhập đúng họ tên và email")
    def fn(st):
        st.setdefault("talent", [])
        if not any(t["e"].lower() == e.lower() for t in st["talent"]):
            st["talent"].append({"n": n, "e": e, "cv": cv})
        return {"ok": True}
    out = mutate(fn)
    audit("talent.joined", e)
    return out

def data_request(b):
    e = need(b, "e", 200)
    if not EMAIL.match(e):
        raise ValueError("Email không hợp lệ")
    def fn(st):
        st.setdefault("del", [])
        if not any(d["e"].lower() == e.lower() and not d.get("done") for d in st["del"]):
            st["del"].append({"e": e})
        return {"ok": True}
    out = mutate(fn)
    audit("data_request.created", e)
    return out

class Handler(BaseHTTPRequestHandler):
    site = "career"
    def log_message(self, *a):
        pass

    def reply(self, code, obj=None, ctype="application/json; charset=utf-8", raw=None):
        body = raw if raw is not None else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 6_000_000:
            raise ValueError("Dữ liệu quá lớn")
        data = json.loads(self.rfile.read(n) or b"{}")
        if not isinstance(data, dict):
            raise ValueError("Dữ liệu không hợp lệ")
        return data

    def limited(self):
        ip, now = self.client_address[0], time.time()
        h = [t for t in HITS.get(ip, []) if now - t < 60]
        h.append(now)
        HITS[ip] = h
        return len(h) > 30

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self.reply(200, ctype="text/html; charset=utf-8", raw=(ROOT / self.site / "index.html").read_bytes())
        if path == "/healthz":
            return self.reply(200, {"ok": True, "site": self.site})
        if path == "/public/jobs":
            return self.reply(200, public_jobs(get_state()[1]))
        if path == "/public/news":
            return self.reply(200, public_news(get_state()[1]))
        if path == "/api/state" and self.site == "ats":
            rev, st = get_state()
            return self.reply(200, {"rev": rev, "state": st})
        if path == "/api/audit" and self.site == "ats":
            with conn() as c:
                rows = [dict(r) for r in c.execute("select * from audit order by id desc limit 100")]
            return self.reply(200, rows)
        self.reply(404, {"error": "Không tìm thấy"})

    def do_POST(self):
        path = urlparse(self.path).path
        routes = {"/public/applications": apply_job, "/public/talent-community": join_talent, "/public/data-requests": data_request}
        if path not in routes:
            return self.reply(404, {"error": "Không tìm thấy"})
        if self.limited():
            return self.reply(429, {"error": "Bạn thao tác quá nhanh, thử lại sau ít phút"})
        try:
            self.reply(200, routes[path](self.body()))
        except (ValueError, json.JSONDecodeError) as e:
            self.reply(422, {"error": str(e) if isinstance(e, ValueError) else "Dữ liệu không hợp lệ"})

    def do_PUT(self):
        if self.path != "/api/state" or self.site != "ats":
            return self.reply(404, {"error": "Không tìm thấy"})
        try:
            b = self.body()
            if not isinstance(b.get("state"), dict) or not isinstance(b.get("rev"), int):
                raise ValueError("Thiếu rev hoặc state")
        except (ValueError, json.JSONDecodeError) as e:
            return self.reply(422, {"error": str(e)})
        rev = put_state(b["rev"], b["state"])
        if rev is None:
            return self.reply(409, {"error": "Dữ liệu đã thay đổi, hãy tải lại"})
        self.reply(200, {"rev": rev})

def serve(site, port):
    h = type("H_" + site, (Handler,), {"site": site})
    srv = ThreadingHTTPServer(("127.0.0.1", port), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

if __name__ == "__main__":
    init()
    cp, ap = int(os.environ.get("CAREER_PORT", 3000)), int(os.environ.get("ATS_PORT", 3001))
    serve("career", cp)
    serve("ats", ap)
    print("Career Site (ứng viên): http://localhost:%d" % cp)
    print("ATS (nội bộ):           http://localhost:%d" % ap)
    print("Nhấn Ctrl+C để dừng.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
