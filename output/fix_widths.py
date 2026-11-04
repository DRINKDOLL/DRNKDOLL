import subprocess, json, os
EDS = "edsdk.py"
FID = "new_doc_115739614049900_d996"
specs = {
 "4m1udmlw": [2200,6104],
 "txwjx8be": [800,3200,4300],
 "6dd0lpsn": [700,1000,3400,3200],
 "1zkipdwx": [1300,2000,3200,1800],
 "24h4lmka": [1990,1050,1050,1050,1050,1050,1064],
 "owr4totx": [1200,800,6300],
 "ra5co7yv": [700,6400,1200],
 "p9uigfii": [1100,2200,2000,3000],
 "syy35cce": [1200,4400,2700],
 "jst7jwgp": [1900,2300,800,3300],
 "pntrq21z": [800,1200,3500,2800],
 "iqmivyjj": [800,1400,6100],
 "vr052uaz": [800,1600,5900],
 "no370q1t": [700,2400,2200,3000],
 "i3poxr2i": [800,2600,4900],
 "k8m2755e": [700,1100,2600,3900],
 "xvyldjns": [2600,5704],
 "pzjs90bh": [2200,6104],
}
for tid, w in specs.items():
    payload = json.dumps({"file_id": FID, "table_id": tid, "mode": "manual", "col_widths_dxa": w})
    r = subprocess.run(["python3", EDS, "call", "doc_set_table_properties", "--json", payload],
                       capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout or "") + (r.stderr or "")
    print(tid, "OK" if '"error"' not in out else out[:200])
