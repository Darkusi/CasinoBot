import requests, json, sys, re
sys.path.insert(0, r"C:\Users\GLOW\Desktop\Code Projects\Coding Planning\app")
import combined

# Check all DEFAULT_SITES for realprizerewards
for s in combined.DEFAULT_SITES:
    if "realprize" in s["domain"].lower():
        print(f"Found: {s['name']} - {s['domain']}")

# Now check all message embeds for URL patterns
cid = combined.DISCORD_CHANNEL_ID
token = combined.DISCORD_BOT_TOKEN
headers = {"Authorization": f"Bot {token}"}
url = f"https://discord.com/api/v10/channels/{cid}/messages"
resp = requests.get(url, headers=headers, params={"limit": 50}, timeout=10)
msgs = resp.json()
print(f"\nTotal messages: {len(msgs)}")
for i, m in enumerate(msgs):
    for e in m.get('embeds', []):
        eu = e.get('url', '')
        if eu:
            # Extract domain from URL
            domain = re.search(r'https?://([^/]+)', eu)
            if domain:
                d = domain.group(1)
                print(f"  [{i}] {d} -> {eu[:80]}")
