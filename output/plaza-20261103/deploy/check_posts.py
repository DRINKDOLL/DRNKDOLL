import json
import urllib.request

names = ["post-miqsxprw", "post-rthumrhv", "post-o2pku9fo", "post-dy2cwnuv", "post-jv2hfyjd"]
print("name             title                raw    html   publish")
for n in names:
    url = "http://127.0.0.1/apis/api.content.halo.run/v1alpha1/posts/" + n
    d = json.load(urllib.request.urlopen(url))
    spec = d["spec"]
    c = spec.get("content") or {}
    raw = c.get("raw") or ""
    html = c.get("content") or ""
    title = (spec.get("title") or "")[:16]
    print("%-16s %-18s %6d %6d  %s" % (n, title, len(raw), len(html), spec.get("publish")))
